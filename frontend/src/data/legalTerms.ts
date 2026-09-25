export type LegalSection = { id: string; title: string; paragraphs: string[] }

export const LEGAL_DRAFT_NOTICE =
  'This text is a product draft for KIYUB. It is not legal advice and should be reviewed by qualified legal counsel before being treated as final terms or a privacy policy.'

export const LEGAL_PLACEHOLDERS = {
  entity: '[KIYUB LEGAL ENTITY NAME]',
  email: '[CONTACT EMAIL]',
  jurisdiction: '[GOVERNING JURISDICTION]',
  dpo: '[DATA PROTECTION CONTACT, IF APPLICABLE]',
}

export const TERMS_EFFECTIVE = 'Effective date: not published'

export const TERMS_SECTIONS: LegalSection[] = [
  {
    id: 'introduction',
    title: 'Introduction',
    paragraphs: [
      `${LEGAL_PLACEHOLDERS.entity} (“KIYUB”) provides an AI-assisted architectural design platform for residential floor-plan concepts, visualization, and architect–client collaboration.`,
      'These Terms govern access to and use of the KIYUB website, application, and related services. If you do not agree, do not use KIYUB.',
    ],
  },
  {
    id: 'acceptance',
    title: 'Acceptance of terms',
    paragraphs: [
      'By creating an account, accepting an invitation, or using KIYUB, you accept these Terms. If you use KIYUB on behalf of an organization, you represent that you have authority to bind that organization.',
    ],
  },
  {
    id: 'eligibility',
    title: 'Eligibility',
    paragraphs: [
      'You must be able to form a binding contract under applicable law. KIYUB is not directed at children. If you are under the age of majority where you live, you may use KIYUB only with a parent or guardian’s permission where that is legally required.',
    ],
  },
  {
    id: 'accounts',
    title: 'Account registration',
    paragraphs: [
      'Some features require an account. You are responsible for the accuracy of registration information and for keeping your credentials confidential. Notify KIYUB at the contact below if you believe an account has been compromised.',
    ],
  },
  {
    id: 'invitations',
    title: 'Invitations and user accounts',
    paragraphs: [
      'Access may be granted by invitation (for example, an architect inviting a client). Invitation links and tokens are confidential. You must not share an invitation intended for another person.',
      'Roles such as client, architect, and studio staff are assigned by the service. You must not attempt to assume a role you were not granted.',
    ],
  },
  {
    id: 'use',
    title: 'Use of KIYUB',
    paragraphs: [
      'KIYUB is a conceptual design and planning tool. You may use it to prepare briefs, generate and review floor-plan concepts, visualize designs, and collaborate on projects you are authorized to access.',
      'You must not interfere with the service, attempt unauthorized access, or use KIYUB to create or distribute unlawful content.',
    ],
  },
  {
    id: 'projects',
    title: 'Projects and project data',
    paragraphs: [
      'Project records, briefs, floor plans, scene documents, comments, and review versions may be stored so that invited participants can work on the same project. You are responsible for the data you submit and for confirming that you have the right to share it with other project participants.',
    ],
  },
  {
    id: 'ai',
    title: 'AI-assisted generation',
    paragraphs: [
      'KIYUB may use automated and AI-assisted processes to propose floor-plan layouts and related visualizations from the information you provide.',
      'AI-generated outputs may contain errors, omissions, or implausible geometry. Outputs are starting points for design discussion, not finished construction documents.',
    ],
  },
  {
    id: 'disclaimer-arch',
    title: 'Architectural disclaimer',
    paragraphs: [
      'KIYUB provides design assistance and visualization. It does not replace licensed architects, engineers, contractors, surveyors, or other qualified professionals.',
      'Generated layouts must not automatically be treated as construction-ready, permit-ready, or code-compliant documents.',
      'You are responsible for reviewing designs before relying on them. Applicable building codes, zoning regulations, structural requirements, accessibility rules, and professional licensing requirements must be independently verified.',
      'KIYUB does not guarantee that any generated design is structurally sound, buildable, or legally compliant.',
    ],
  },
  {
    id: 'responsibilities',
    title: 'User responsibilities',
    paragraphs: [
      'You are responsible for decisions you make using KIYUB output, for obtaining professional review where required, and for complying with laws that apply to your project.',
    ],
  },
  {
    id: 'ip',
    title: 'Intellectual property',
    paragraphs: [
      'KIYUB and its licensors retain rights in the software, branding, and interface. These Terms do not transfer ownership of KIYUB’s software to you.',
    ],
  },
  {
    id: 'ugc',
    title: 'User-generated content',
    paragraphs: [
      'You retain rights in content you upload (such as briefs, comments, and project names), subject to the license needed for KIYUB to store and display that content to authorized project participants.',
    ],
  },
  {
    id: 'generated',
    title: 'Generated design content',
    paragraphs: [
      'Subject to these Terms and applicable law, you may use generated floor-plan concepts and visualizations for your project’s design process. KIYUB does not warrant uniqueness or non-infringement of generated output.',
    ],
  },
  {
    id: 'prohibited',
    title: 'Prohibited use',
    paragraphs: [
      'You may not use KIYUB to attempt to break security, scrape the service beyond ordinary use, impersonate others, or submit content you do not have the right to use.',
    ],
  },
  {
    id: 'third-party',
    title: 'Third-party services',
    paragraphs: [
      'KIYUB may rely on third-party hosting, authentication, and related infrastructure. Those services have their own terms. KIYUB is not responsible for third-party services it does not control.',
    ],
  },
  {
    id: 'availability',
    title: 'Availability and changes to service',
    paragraphs: [
      'KIYUB may change, suspend, or discontinue features. The service may be unavailable from time to time for maintenance or reasons outside KIYUB’s control.',
    ],
  },
  {
    id: 'liability',
    title: 'Limitation of liability',
    paragraphs: [
      'To the fullest extent permitted by law, KIYUB is not liable for indirect, incidental, special, or consequential damages, or for losses arising from reliance on generated designs without independent professional review. Nothing in these Terms limits liability that cannot be limited under applicable law.',
    ],
  },
  {
    id: 'warranties',
    title: 'Disclaimer of warranties',
    paragraphs: [
      'KIYUB is provided “as is” and “as available.” KIYUB disclaims implied warranties of merchantability, fitness for a particular purpose, and non-infringement, except where such disclaimers are not permitted.',
    ],
  },
  {
    id: 'termination',
    title: 'Termination',
    paragraphs: [
      'You may stop using KIYUB at any time. KIYUB may suspend or terminate access if these Terms are violated or if the service is discontinued.',
    ],
  },
  {
    id: 'law',
    title: 'Governing law',
    paragraphs: [
      `These Terms are governed by the laws of ${LEGAL_PLACEHOLDERS.jurisdiction}, excluding conflict-of-law rules, unless mandatory consumer law in your country applies.`,
    ],
  },
  {
    id: 'changes',
    title: 'Changes to terms',
    paragraphs: [
      'KIYUB may update these Terms. Continued use after an update constitutes acceptance of the revised Terms where permitted by law. Material changes should be indicated by updating the effective date.',
    ],
  },
  {
    id: 'contact',
    title: 'Contact information',
    paragraphs: [
      `Questions about these Terms: ${LEGAL_PLACEHOLDERS.email}.`,
    ],
  },
]
