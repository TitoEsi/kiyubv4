import { LEGAL_PLACEHOLDERS, type LegalSection } from './legalTerms'

export const PRIVACY_EFFECTIVE = 'Effective date: not published'

export const PRIVACY_SECTIONS: LegalSection[] = [
  {
    id: 'introduction',
    title: 'Introduction',
    paragraphs: [
      `This Privacy Policy describes how ${LEGAL_PLACEHOLDERS.entity} (“KIYUB”) handles information in connection with the KIYUB application and website.`,
      'It is a product draft. Practices may change as the service develops. It does not claim compliance with a specific privacy framework unless separately established.',
    ],
  },
  {
    id: 'collect',
    title: 'Information We Collect',
    paragraphs: [
      'KIYUB may collect information you provide, information created while you use the product, and limited technical information needed to operate the service.',
    ],
  },
  {
    id: 'account',
    title: 'Account Information',
    paragraphs: [
      'If you register or accept an invitation, KIYUB may store your email address, display name, role, and account status so you can sign in and be recognized on projects.',
    ],
  },
  {
    id: 'auth',
    title: 'Authentication Information',
    paragraphs: [
      'Sign-in is handled through the configured authentication provider. KIYUB receives session or identity information needed to recognize you. Password handling follows that provider; this policy does not describe a specific password-storage method beyond what that provider implements.',
    ],
  },
  {
    id: 'project',
    title: 'Project and Floor-Plan Data',
    paragraphs: [
      'KIYUB stores project records you create or join, including briefs, questionnaires, generated or edited floor plans, scene documents, working copies, and submitted review versions. This data exists so authorized participants can view and continue work on the same project.',
    ],
  },
  {
    id: 'collab',
    title: 'Architect/Client Collaboration Data',
    paragraphs: [
      'Comments, pins, invitations, review status, and notifications may be stored and shown to other people on the same project. Do not put information in comments or briefs that you do not want those participants to see.',
    ],
  },
  {
    id: 'technical',
    title: 'Technical and Usage Information',
    paragraphs: [
      'Servers and browsers necessarily process technical data such as IP address, user agent, and request logs as part of operating a web application. KIYUB does not claim a separate anonymous analytics product in this draft.',
    ],
  },
  {
    id: 'use',
    title: 'How We Use Information',
    paragraphs: [
      'Information is used to provide accounts, run projects, generate and display designs, send invitations and in-app notices, maintain security, and operate the service. This draft does not describe additional marketing programs.',
    ],
  },
  {
    id: 'ai',
    title: 'AI-Assisted Processing',
    paragraphs: [
      'Information you submit to generation features (such as site and program requirements) may be processed by KIYUB and by the generation services or models configured for the deployment, in order to produce floor-plan candidates and related output.',
      'Do not submit sensitive personal data in briefs unless you accept that it may be processed for generation.',
    ],
  },
  {
    id: 'share',
    title: 'How We Share Information',
    paragraphs: [
      'Project data is shared with other authorized users on that project (for example, the assigned architect and client). KIYUB may also use infrastructure providers that process data to host the application.',
      'KIYUB does not sell personal information in this draft. Legal requests may require disclosure where the law requires it.',
    ],
  },
  {
    id: 'third',
    title: 'Third-Party Services',
    paragraphs: [
      'Authentication, database hosting, email delivery, and similar functions may be provided by third parties (for example, a configured Auth and database host). Their processing is governed by their own policies in addition to this draft.',
    ],
  },
  {
    id: 'storage',
    title: 'Data Storage and Security',
    paragraphs: [
      'Project and account data are stored in the configured backend and database. This draft does not claim a specific encryption standard, certification, or security audit. You should assume ordinary internet risks apply.',
    ],
  },
  {
    id: 'retention',
    title: 'Data Retention',
    paragraphs: [
      'Data is retained while an account or project remains on the service, and may remain in backups for a period afterward. This draft does not state a fixed retention period because one has not been published.',
    ],
  },
  {
    id: 'rights',
    title: 'User Rights',
    paragraphs: [
      'Depending on where you live, you may have rights to access, correct, or request deletion of personal information. KIYUB does not claim that a self-service deletion or export tool exists in the current product. Requests may be sent to the contact below and will be handled as the operator is able.',
    ],
  },
  {
    id: 'cookies',
    title: 'Cookies and Similar Technologies',
    paragraphs: [
      'The application uses storage needed for sign-in sessions and theme preference. This draft does not describe a separate advertising cookie program.',
    ],
  },
  {
    id: 'children',
    title: "Children's Privacy",
    paragraphs: [
      'KIYUB is not directed to children. If you believe a child has provided personal information, contact the address below.',
    ],
  },
  {
    id: 'transfers',
    title: 'International Data Transfers',
    paragraphs: [
      'If you access KIYUB from another country, information may be processed where the hosting and authentication providers operate. This draft does not describe a specific transfer mechanism.',
    ],
  },
  {
    id: 'changes',
    title: 'Changes to This Privacy Policy',
    paragraphs: [
      'This policy may be updated. The effective date should be revised when a published version changes.',
    ],
  },
  {
    id: 'contact',
    title: 'Contact Information',
    paragraphs: [
      `Privacy questions: ${LEGAL_PLACEHOLDERS.email}. Data protection contact, if applicable: ${LEGAL_PLACEHOLDERS.dpo}.`,
    ],
  },
]
