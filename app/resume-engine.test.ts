import assert from 'node:assert/strict';
import test from 'node:test';

import { mapInputs } from './resume-engine.ts';

const profile = {
  basics: { name: 'Test Candidate', headline: 'Security Engineer', email: 'test@example.com' },
  summary: 'Security engineer focused on defensible cloud automation.',
  experience: [{
    id: 'experience-cloud', company: 'Example GmbH', position: 'Security Intern',
    bullets: [
      { id: 'experience-cloud-documentation', text: 'Wrote internal documentation.', tags: ['documentation'] },
      { id: 'experience-cloud-alerts', text: 'Investigated AWS security alerts.', tags: ['aws', 'cloud-security', 'monitoring', 'incident-response'] },
    ],
  }],
  education: [],
  skills: [
    { id: 'skill-cloud', name: 'Cloud Security', keywords: ['AWS', 'IAM', 'CloudTrail'], tags: ['aws', 'cloud-security', 'monitoring'] },
    { id: 'skill-iac', name: 'Infrastructure as Code', keywords: ['Terraform'], tags: ['terraform'] },
  ],
  projects: [{
    id: 'project-automation', name: 'Security Automation Lab',
    description: 'Automated security checks using Python.', keywords: ['Python'], tags: ['python', 'automation', 'security'],
  }],
};

const vacancy = {
  job: {
    title: 'Cloud Security Engineer',
    requirements: [
      'AWS cloud security monitoring experience',
      'Terraform and Pulumi production experience',
      'Production Kubernetes administration',
    ],
    responsibilities: ['Automate security checks using Python'],
    nice_to_haves: [],
  },
};

test('classifies matched, partial, and unsupported requirements with traceable evidence', () => {
  const report = mapInputs(profile, vacancy);
  const byRequirement = Object.fromEntries(report.coverage.map((item) => [item.requirement, item]));

  assert.equal(byRequirement['AWS cloud security monitoring experience'].status, 'matched');
  assert.equal(byRequirement['AWS cloud security monitoring experience'].source, 'requirement');
  assert.ok(byRequirement['AWS cloud security monitoring experience'].evidence.some((item) => item.id === 'skill-cloud'));
  assert.ok(byRequirement['AWS cloud security monitoring experience'].evidence.some((item) => item.id === 'experience-cloud-alerts'));
  assert.equal(byRequirement['Terraform and Pulumi production experience'].status, 'partial');
  assert.equal(byRequirement['Production Kubernetes administration'].status, 'unsupported');
  assert.equal(byRequirement['Production Kubernetes administration'].evidence.length, 0);
  assert.equal(byRequirement['Automate security checks using Python'].status, 'matched');
  assert.equal(byRequirement['Automate security checks using Python'].source, 'responsibility');
  assert.deepEqual(report.coverageSummary, { matched: 2, partial: 1, unsupported: 1 });
  assert.equal(report.coveragePercent, 63);
});

test('ranks supported experience evidence without changing its factual text', () => {
  const report = mapInputs(profile, vacancy);
  assert.deepEqual(report.resume.experience[0].highlights, [
    'Investigated AWS security alerts.',
    'Wrote internal documentation.',
  ]);
  assert.equal(report.resume.experience[0].highlights.includes('Production Kubernetes administration'), false);
  assert.ok(report.warnings.some((warning) => warning.includes('no supporting profile evidence')));
});
