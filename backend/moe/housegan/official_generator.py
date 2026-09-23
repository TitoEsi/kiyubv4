"""Minimal official House-GAN++ generator (Conv-MPN).

THIS CODE CAN ONLY BE USED FOR RESEARCH PURPOSES.

Vendored (architecture-faithful, inference-only) from:
  https://github.com/ennauata/houseganpp/blob/main/models/models.py
  Nauata et al., House-GAN++, CVPR 2021.

Upstream license: GNU GPL v3. Do not vendor test.py, the RPLAN dataloader,
pygraphviz, or OpenCV drawing utilities.

Do not load this network with strict=False.
"""
from __future__ import annotations

import torch
import torch.nn as nn
from torch.nn.utils import spectral_norm


def conv_block(
    in_channels,
    out_channels,
    k,
    s,
    p,
    act=None,
    upsample=False,
    spec_norm=False,
    batch_norm=False,
):
    block = []
    if upsample:
        conv = torch.nn.ConvTranspose2d(
            in_channels, out_channels, kernel_size=k, stride=s, padding=p, bias=True
        )
    else:
        conv = torch.nn.Conv2d(
            in_channels, out_channels, kernel_size=k, stride=s, padding=p, bias=True
        )
    if spec_norm:
        conv = spectral_norm(conv)
    block.append(conv)
    if batch_norm:
        block.append(nn.BatchNorm2d(out_channels))
    if act and "leaky" in act:
        block.append(torch.nn.LeakyReLU(0.1, inplace=True))
    elif act and "relu" in act:
        block.append(torch.nn.ReLU(inplace=True))
    return block


class CMP(nn.Module):
    """Convolutional message passing (official HouseGAN++)."""

    def __init__(self, in_channels):
        super().__init__()
        self.in_channels = in_channels
        self.encoder = nn.Sequential(
            *conv_block(3 * in_channels, 2 * in_channels, 3, 1, 1, act="leaky"),
            *conv_block(2 * in_channels, 2 * in_channels, 3, 1, 1, act="leaky"),
            *conv_block(2 * in_channels, in_channels, 3, 1, 1, act="leaky"),
        )

    def forward(self, feats, edges=None):
        dtype, device = feats.dtype, feats.device
        if edges is None or edges.numel() == 0:
            zeros = torch.zeros(
                feats.size(0), feats.shape[-3], feats.shape[-1], feats.shape[-1],
                dtype=dtype, device=device,
            )
            enc_in = torch.cat([feats, zeros, zeros], 1)
            return self.encoder(enc_in)
        edges = edges.view(-1, 3)
        V = feats.size(0)
        pooled_v_pos = torch.zeros(
            V, feats.shape[-3], feats.shape[-1], feats.shape[-1], dtype=dtype, device=device
        )
        pooled_v_neg = torch.zeros(
            V, feats.shape[-3], feats.shape[-1], feats.shape[-1], dtype=dtype, device=device
        )
        pos_inds = torch.where(edges[:, 1] > 0)
        pos_v_src = torch.cat([edges[pos_inds[0], 0], edges[pos_inds[0], 2]]).long()
        pos_v_dst = torch.cat([edges[pos_inds[0], 2], edges[pos_inds[0], 0]]).long()
        pos_vecs_src = feats[pos_v_src.contiguous()]
        pos_v_dst = pos_v_dst.view(-1, 1, 1, 1).expand_as(pos_vecs_src).to(device)
        pooled_v_pos = torch.scatter_add(pooled_v_pos, 0, pos_v_dst, pos_vecs_src)
        neg_inds = torch.where(edges[:, 1] < 0)
        neg_v_src = torch.cat([edges[neg_inds[0], 0], edges[neg_inds[0], 2]]).long()
        neg_v_dst = torch.cat([edges[neg_inds[0], 2], edges[neg_inds[0], 0]]).long()
        neg_vecs_src = feats[neg_v_src.contiguous()]
        neg_v_dst = neg_v_dst.view(-1, 1, 1, 1).expand_as(neg_vecs_src).to(device)
        pooled_v_neg = torch.scatter_add(pooled_v_neg, 0, neg_v_dst, neg_vecs_src)
        enc_in = torch.cat([feats, pooled_v_pos, pooled_v_neg], 1)
        return self.encoder(enc_in)


class Generator(nn.Module):
    """Official House-GAN++ relational generator."""

    def __init__(self):
        super().__init__()
        self.init_size = 32 // 4
        self.l1 = nn.Sequential(nn.Linear(146, 16 * self.init_size ** 2))
        self.upsample_1 = nn.Sequential(*conv_block(16, 16, 4, 2, 1, act="leaky", upsample=True))
        self.upsample_2 = nn.Sequential(*conv_block(16, 16, 4, 2, 1, act="leaky", upsample=True))
        self.upsample_3 = nn.Sequential(*conv_block(16, 16, 4, 2, 1, act="leaky", upsample=True))
        self.cmp_1 = CMP(in_channels=16)
        self.cmp_2 = CMP(in_channels=16)
        self.cmp_3 = CMP(in_channels=16)
        self.cmp_4 = CMP(in_channels=16)
        self.decoder = nn.Sequential(
            *conv_block(16, 256, 3, 1, 1, act="leaky"),
            *conv_block(256, 128, 3, 1, 1, act="leaky"),
            *conv_block(128, 1, 3, 1, 1, act="tanh"),
        )
        self.l1_fixed = nn.Sequential(nn.Linear(1, 1 * self.init_size ** 2))
        self.enc_1 = nn.Sequential(
            *conv_block(2, 32, 3, 2, 1, act="leaky"),
            *conv_block(32, 32, 3, 2, 1, act="leaky"),
            *conv_block(32, 16, 3, 2, 1, act="leaky"),
        )
        self.enc_2 = nn.Sequential(
            *conv_block(32, 32, 3, 1, 1, act="leaky"),
            *conv_block(32, 16, 3, 1, 1, act="leaky"),
        )

    def forward(self, z, given_m=None, given_y=None, given_w=None, given_v=None):
        z = z.view(-1, 128)
        y = given_y.view(-1, 18)
        z = torch.cat([z, y], 1)
        x = self.l1(z)
        f = x.view(-1, 16, self.init_size, self.init_size)
        m = self.enc_1(given_m)
        f = torch.cat([f, m], 1)
        f = self.enc_2(f)
        x = self.cmp_1(f, given_w).view(-1, *f.shape[1:])
        x = self.upsample_1(x)
        x = self.cmp_2(x, given_w).view(-1, *x.shape[1:])
        x = self.upsample_2(x)
        x = self.cmp_3(x, given_w).view(-1, *x.shape[1:])
        x = self.upsample_3(x)
        x = self.cmp_4(x, given_w).view(-1, *x.shape[1:])
        x = self.decoder(x.view(-1, x.shape[1], *x.shape[2:]))
        x = x.view(-1, *x.shape[2:])
        return x


OfficialGenerator = Generator
