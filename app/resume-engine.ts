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
};

const record = (value: unknown): JsonRecord => value && typeof value === 'object' && !Array.isArray(value) ? value as JsonRecord : {};
const array = (value: unknown): unknown[] => Array.isArray(value) ? value : [];
const text = (...values: unknown[]) => values.find((value) => typeof value === 'string' && value.trim())?.toString().trim() ?? '';
const strings = (value: unknown) => array(value).map((item) => typeof item === 'string' ? item.trim() : '').filter(Boolean);

const tokens = (value: unknown) => {
  const source = typeof value === 'string' ? value : JSON.stringify(value ?? '');
  return [...new Set(source.toLowerCase().match(/[a-z0-9+#.]{2,}/g) ?? [])]
    .filter((word) => !['and', 'the', 'with', 'for', 'from', 'that', 'this', 'your', 'you', 'our', 'are'].includes(word));
};

const relevance = (value: unknown, vacancyTerms: string[]) => {
  const own = new Set(tokens(value));
  return vacancyTerms.reduce((score, term) => score + (own.has(term) ? 1 : 0), 0);
};

export function mapInputs(profileInput: unknown, vacancyInput: unknown): MappingReport {
  const profile = record(profileInput);
  const basics = record(profile.basics ?? profile.profile ?? profile.personal);
  const job = record(record(vacancyInput).job ?? vacancyInput);
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

  const experience = array(profile.experience ?? profile.work).map((raw) => {
    const item = record(raw);
    const highlights = strings(item.highlights ?? item.bullets ?? item.achievements);
    return {
      company: text(item.company, item.name, item.organization),
      position: text(item.position, item.role, item.title),
      date: text(item.date, item.period, [item.startDate, item.endDate].filter(Boolean).join(' – ')),
      summary: text(item.summary, item.description),
      highlights,
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

  const skills = array(profile.skills).map((raw) => {
    if (typeof raw === 'string') return { name: raw, keywords: [] as string[], score: relevance(raw, vacancyTerms) };
    const item = record(raw);
    const name = text(item.name, item.category, item.title);
    const keywords = strings(item.keywords ?? item.items ?? item.skills);
    return { name, keywords, score: relevance({ name, keywords }, vacancyTerms) };
  }).filter((item) => item.name || item.keywords.length).sort((a, b) => b.score - a.score);
  if (skills.length) mapped.push(`${skills.length} skill groups`); else warnings.push('No skills were found.');

  const projects = array(profile.projects).map((raw) => {
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
  };
}
