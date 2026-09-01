export type JsonRecord = Record<string, unknown>;

export type ResumeData = {
  basics: { name: string; headline: string; email: string; phone: string; location: string; website: string };
  summary: string;
  experience: Array<{ company: string; position: string; date: string; summary: string; highlights: string[] }>;
  education: Array<{ institution: string; degree: string; date: string; summary: string }>;
  skills: Array<{ name: string; keywords: string[]; score: number }>;
  projects: Array<{ name: string; description: string; url: string; keywords: string[]; score: number }>;
};

export type MappingReport = {
  resume: ResumeData;
  mapped: string[];
  warnings: string[];
  ignored: string[];
  vacancyTerms: string[];
  coverage: RequirementCoverage[];
  coverageSummary: { matched: number; partial: number; unsupported: number };
  coveragePercent: number;
};

export type EvidenceMatch = {
  id: string;
  type: 'skill' | 'project' | 'experience';
  label: string;
  matchedTerms: string[];
  score: number;
};

export type RequirementCoverage = {
  requirement: string;
  source: 'requirement' | 'responsibility' | 'nice_to_have';
  status: 'matched' | 'partial' | 'unsupported';
  score: number;
  evidence: EvidenceMatch[];
};

type CoverageInput = Pick<RequirementCoverage, 'requirement' | 'source'>;

const record = (value: unknown): JsonRecord => value && typeof value === 'object' && !Array.isArray(value) ? value as JsonRecord : {};
const array = (value: unknown): unknown[] => Array.isArray(value) ? value : [];
const text = (...values: unknown[]) => values.find((value) => typeof value === 'string' && value.trim())?.toString().trim() ?? '';
const strings = (value: unknown) => array(value).map((item) => typeof item === 'string' ? item.trim() : '').filter(Boolean);
const contentStrings = (value: unknown) => array(value).map((item) => typeof item === 'string' ? item.trim() : text(record(item).text, record(item).description)).filter(Boolean);
const stableId = (prefix: string, value: unknown, index: number) => text(record(value).id) || `${prefix}-${index + 1}`;

const aliases: Record<string, string[]> = {
  aws: ['amazon', 'cloudtrail', 'guardduty', 'iam'],
  cybersecurity: ['security', 'cyber', 'infosec'],
  automation: ['workflow', 'n8n', 'zapier', 'power', 'automate'],
  siem: ['splunk', 'sentinel', 'monitoring'],
  python: ['scripting'],
};

const tokens = (value: unknown) => {
  const source = typeof value === 'string' ? value : JSON.stringify(value ?? '');
  return [...new Set(source.toLowerCase().match(/[a-z0-9+#.]{2,}/g) ?? [])]
    .filter((word) => !['and', 'the', 'with', 'for', 'from', 'that', 'this', 'your', 'you', 'our', 'are'].includes(word));
};

const relevance = (value: unknown, vacancyTerms: string[]) => {
  const own = new Set(tokens(value));
  return vacancyTerms.reduce((score, term) => score + (own.has(term) ? 1 : 0), 0);
};

const expandedTokens = (value: unknown) => {
  const own = new Set(tokens(value));
  for (const [canonical, related] of Object.entries(aliases)) {
    if (own.has(canonical) || related.some((term) => own.has(term))) {
      own.add(canonical);
      related.forEach((term) => own.add(term));
    }
  }
  return [...own];
};

function buildCoverage(requirements: CoverageInput[], evidence: Array<Omit<EvidenceMatch, 'matchedTerms' | 'score'> & { content: unknown; weight: number }>): RequirementCoverage[] {
  return requirements.map(({ requirement, source }) => {
    const requiredTerms = expandedTokens(requirement);
    const matches = evidence.map((item) => {
      const evidenceTerms = new Set(expandedTokens(item.content));
      const matchedTerms = requiredTerms.filter((term) => evidenceTerms.has(term));
      return { id: item.id, type: item.type, label: item.label, matchedTerms, score: matchedTerms.length * item.weight };
    }).filter((item) => item.score > 0).sort((a, b) => b.score - a.score).slice(0, 5);
    const score = matches.reduce((sum, item) => sum + item.score, 0);
    const uniqueMatched = new Set(matches.flatMap((item) => item.matchedTerms)).size;
    const ratio = requiredTerms.length ? uniqueMatched / requiredTerms.length : 0;
    const status = score >= 8 || ratio >= 0.6 ? 'matched' : score >= 3 || ratio >= 0.25 ? 'partial' : 'unsupported';
    return { requirement, source, status, score, evidence: matches };
  });
}

export function mapInputs(profileInput: unknown, vacancyInput: unknown): MappingReport {
  const profile = record(profileInput);
  const basics = record(profile.basics ?? profile.profile ?? profile.personal);
  const job = record(record(vacancyInput).job ?? vacancyInput);
  const requirements: CoverageInput[] = [
    ...strings(job.requirements).map((requirement) => ({ requirement, source: 'requirement' as const })),
    ...strings(job.responsibilities).map((requirement) => ({ requirement, source: 'responsibility' as const })),
    ...strings(job.nice_to_haves ?? job.niceToHaves).map((requirement) => ({ requirement, source: 'nice_to_have' as const })),
  ];
  const vacancyTerms = tokens({
    title: job.title,
    responsibilities: job.responsibilities ?? job.tasks,
    requirements: job.requirements,
    niceToHaves: job.nice_to_haves ?? job.niceToHaves,
    skills: job.skills,
  });
  const mapped: string[] = [];
  const warnings: string[] = [];

  const mappedBasics = {
    name: text(basics.name, profile.name),
    headline: text(basics.headline, basics.title, profile.headline, profile.title),
    email: text(basics.email, profile.email),
    phone: text(basics.phone, basics.phoneNumber, profile.phone),
    location: text(basics.location, basics.address, profile.location),
    website: text(basics.website, basics.url, profile.website),
  };
  if (mappedBasics.name) mapped.push('Name'); else warnings.push('Candidate name is missing.');
  if (mappedBasics.headline) mapped.push('Headline'); else warnings.push('Professional headline is missing.');
  if (mappedBasics.email) mapped.push('Email');

  const rawExperience = array(profile.experience ?? profile.work);
  const experience = rawExperience.map((raw) => {
    const item = record(raw);
    const highlights = contentStrings(item.highlights ?? item.bullets ?? item.achievements);
    return {
      company: text(item.company, item.name, item.organization),
      position: text(item.position, item.role, item.title),
      date: text(item.date, item.period, [item.startDate, item.endDate].filter(Boolean).join(' – ')),
      summary: text(item.summary, item.description),
      highlights: highlights.sort((a, b) => relevance(b, vacancyTerms) - relevance(a, vacancyTerms)),
    };
  }).filter((item) => item.company || item.position);
  if (experience.length) mapped.push(`${experience.length} experience entries`); else warnings.push('No experience entries were found.');

  const education = array(profile.education).map((raw) => {
    const item = record(raw);
    return {
      institution: text(item.institution, item.school, item.organization),
      degree: text(item.degree, item.area, item.studyType, item.title),
      date: text(item.date, item.period, [item.startDate, item.endDate].filter(Boolean).join(' – ')),
      summary: text(item.summary, item.description),
    };
  }).filter((item) => item.institution || item.degree);
  if (education.length) mapped.push(`${education.length} education entries`);

  const rawSkills = array(profile.skills);
  const skills = rawSkills.map((raw) => {
    if (typeof raw === 'string') return { name: raw, keywords: [] as string[], score: relevance(raw, vacancyTerms) };
    const item = record(raw);
    const name = text(item.name, item.category, item.title);
    const keywords = strings(item.keywords ?? item.items ?? item.skills);
    return { name, keywords, score: relevance({ name, keywords }, vacancyTerms) };
  }).filter((item) => item.name || item.keywords.length).sort((a, b) => b.score - a.score);
  if (skills.length) mapped.push(`${skills.length} skill groups`); else warnings.push('No skills were found.');

  const rawProjects = array(profile.projects);
  const projects = rawProjects.map((raw) => {
    const item = record(raw);
    const name = text(item.name, item.title);
    const description = text(item.description, item.summary);
    const keywords = strings(item.keywords ?? item.technologies ?? item.skills);
    return { name, description, url: text(item.url, item.website), keywords, score: relevance({ name, description, keywords }, vacancyTerms) };
  }).filter((item) => item.name || item.description).sort((a, b) => b.score - a.score);
  if (projects.length) mapped.push(`${projects.length} projects`);

  const known = new Set(['basics', 'profile', 'personal', 'name', 'headline', 'title', 'email', 'phone', 'location', 'website', 'summary', 'objective', 'experience', 'work', 'education', 'skills', 'projects']);
  const ignored = Object.keys(profile).filter((key) => !known.has(key));
  if (!vacancyTerms.length) warnings.push('The vacancy contains no usable requirements or responsibilities for ranking.');

  const evidence: Array<Omit<EvidenceMatch, 'matchedTerms' | 'score'> & { content: unknown; weight: number }> = [];
  rawSkills.forEach((raw, index) => {
    const item = typeof raw === 'string' ? { name: raw } : record(raw);
    evidence.push({ id: stableId('skill', item, index), type: 'skill', label: text(item.name, item.category, item.title, raw), content: { item, tags: item.tags }, weight: 5 });
  });
  rawProjects.forEach((raw, index) => {
    const item = record(raw);
    evidence.push({ id: stableId('project', item, index), type: 'project', label: text(item.name, item.title, `Project ${index + 1}`), content: { item, tags: item.tags }, weight: 3 });
  });
  rawExperience.forEach((raw, experienceIndex) => {
    const item = record(raw);
    array(item.highlights ?? item.bullets ?? item.achievements).forEach((bullet, bulletIndex) => {
      const bulletRecord = record(bullet);
      const bulletText = typeof bullet === 'string' ? bullet : text(bulletRecord.text, bulletRecord.description);
      evidence.push({ id: text(bulletRecord.id) || `${stableId('experience', item, experienceIndex)}-bullet-${bulletIndex + 1}`, type: 'experience', label: bulletText, content: { text: bulletText, tags: bulletRecord.tags }, weight: 4 });
    });
  });
  const coverage = buildCoverage(requirements, evidence);
  const coverageSummary = {
    matched: coverage.filter((item) => item.status === 'matched').length,
    partial: coverage.filter((item) => item.status === 'partial').length,
    unsupported: coverage.filter((item) => item.status === 'unsupported').length,
  };
  const coveragePercent = coverage.length
    ? Math.round(((coverageSummary.matched + coverageSummary.partial * 0.5) / coverage.length) * 100)
    : 0;
  if (coverageSummary.unsupported) warnings.push(`${coverageSummary.unsupported} vacancy requirements have no supporting profile evidence.`);

  return {
    resume: {
      basics: mappedBasics,
      summary: text(profile.summary, profile.objective, basics.summary),
      experience,
      education,
      skills,
      projects,
    },
    mapped,
    warnings,
    ignored,
    vacancyTerms,
    coverage,
    coverageSummary,
    coveragePercent,
  };
}
