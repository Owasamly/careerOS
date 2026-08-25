'use client';

import { ChangeEvent, useMemo, useState } from 'react';
import { mapInputs, type MappingReport } from './resume-engine';

type InputMode = 'paste' | 'upload';
type Step = 'profile' | 'vacancy' | 'tailoring';

const exampleProfile = `{
  "basics": {
    "name": "Osama Nurhussen Kahsay",
    "headline": "Cybersecurity M.Sc. Student",
    "email": "you@example.com"
  },
  "summary": "Security and automation engineer...",
  "experience": [],
  "education": [],
  "skills": [],
  "projects": []
}`;

const exampleVacancy = `{
  "job": {
    "title": "Cloud Security Engineer",
    "company": "Example GmbH",
    "location": "Munich, Germany",
    "responsibilities": [],
    "requirements": [],
    "nice_to_haves": []
  }
}`;

const steps: { id: Step; label: string; hint: string }[] = [
  { id: 'profile', label: 'Your profile', hint: 'Canonical career data' },
  { id: 'vacancy', label: 'Job vacancy', hint: 'Role and requirements' },
  { id: 'tailoring', label: 'Tailoring rules', hint: 'Output and emphasis' },
];

function JsonInput({ label, description, value, setValue, mode, setMode, placeholder }: {
  label: string; description: string; value: string; setValue: (value: string) => void;
  mode: InputMode; setMode: (mode: InputMode) => void; placeholder: string;
}) {
  const status = useMemo(() => {
    if (!value.trim()) return { label: 'Waiting for data', tone: 'quiet' };
    try { JSON.parse(value); return { label: 'Valid JSON', tone: 'good' }; }
    catch { return { label: 'Needs attention', tone: 'bad' }; }
  }, [value]);

  const readFile = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => setValue(String(reader.result ?? ''));
    reader.readAsText(file);
  };

  return (
    <section className="input-card">
      <div className="card-heading">
        <div><p className="eyebrow">{label}</p><p className="card-description">{description}</p></div>
        <span className={`status ${status.tone}`}>{status.label}</span>
      </div>
      <div className="segmented" aria-label={`${label} input method`}>
        <button className={mode === 'paste' ? 'active' : ''} onClick={() => setMode('paste')}>Paste JSON</button>
        <button className={mode === 'upload' ? 'active' : ''} onClick={() => setMode('upload')}>Upload file</button>
      </div>
      {mode === 'paste' ? (
        <textarea aria-label={label} value={value} onChange={(event) => setValue(event.target.value)} placeholder={placeholder} spellCheck={false} />
      ) : (
        <label className="dropzone">
          <span className="upload-mark">↑</span><strong>Choose a JSON file</strong>
          <span>or drag it here later when uploads are connected</span>
          <input type="file" accept="application/json,.json" onChange={readFile} />
        </label>
      )}
    </section>
  );
}

export default function Home() {
  const [activeStep, setActiveStep] = useState<Step>('profile');
  const [profileMode, setProfileMode] = useState<InputMode>('paste');
  const [vacancyMode, setVacancyMode] = useState<InputMode>('paste');
  const [profile, setProfile] = useState(exampleProfile);
  const [vacancy, setVacancy] = useState(exampleVacancy);
  const [strength, setStrength] = useState('Balanced');
  const [pages, setPages] = useState('2 pages');
  const [reviewOpen, setReviewOpen] = useState(false);
  const [report, setReport] = useState<MappingReport | null>(null);
  const [generating, setGenerating] = useState(false);

  const bothValid = useMemo(() => {
    try { JSON.parse(profile); JSON.parse(vacancy); return true; } catch { return false; }
  }, [profile, vacancy]);

  const reviewMapping = () => {
    try {
      setReport(mapInputs(JSON.parse(profile), JSON.parse(vacancy)));
      setReviewOpen(true);
    } catch {
      setReport(null);
    }
  };

  const generatePdf = async () => {
    if (!report) return;
    setGenerating(true);
    try {
      const { downloadResumePdf } = await import('./resume-pdf');
      await downloadResumePdf(report.resume);
    }
    finally { setGenerating(false); }
  };

  const downloadJson = () => {
    if (!report) return;
    const blob = new Blob([JSON.stringify(report.resume, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = 'adapted-cv.json';
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="Adapt My CV home"><span className="brand-mark">A</span><span>Adapt My CV</span></a>
        <div className="topbar-center"><span className="draft-dot" /> New tailoring draft</div>
        <div className="topbar-actions"><button className="text-button">Schema guide</button><button className="avatar" aria-label="Profile menu">ON</button></div>
      </header>

      <div className="workspace" id="top">
        <aside className="steps-panel">
          <p className="panel-label">Build your input</p>
          <nav aria-label="Tailoring steps">
            {steps.map((step, index) => (
              <button key={step.id} className={`step ${activeStep === step.id ? 'selected' : ''}`} onClick={() => setActiveStep(step.id)}>
                <span className="step-number">{index + 1}</span>
                <span><strong>{step.label}</strong><small>{step.hint}</small></span>
              </button>
            ))}
          </nav>
          <div className="privacy-note"><span>◆</span><div><strong>Your data stays deliberate</strong><p>Nothing is sent until you review the tailoring brief.</p></div></div>
        </aside>

        <section className="main-panel">
          <div className="page-intro">
            <p className="eyebrow accent">Workspace setup</p>
            <h1>Turn a vacancy into a focused CV.</h1>
            <p>Bring your complete career profile and the role you want. The local rule engine maps known fields, ranks relevant skills and projects, and renders a PDF without AI.</p>
          </div>

          <div className="input-grid">
            <JsonInput label="Candidate profile" description="The source of truth. Keep every role, project, skill and achievement here." value={profile} setValue={setProfile} mode={profileMode} setMode={setProfileMode} placeholder="Paste your canonical profile JSON" />
            <JsonInput label="Job vacancy" description="Use structured fields for responsibilities, requirements and nice-to-haves." value={vacancy} setValue={setVacancy} mode={vacancyMode} setMode={setVacancyMode} placeholder="Paste the structured vacancy JSON" />
          </div>

          <section className="rules-card">
            <div className="card-heading"><div><p className="eyebrow">Tailoring rules</p><p className="card-description">Control how much changes and what the output must respect.</p></div><span className="optional">Optional</span></div>
            <div className="rule-grid">
              <label>Selection strength<select value={strength} onChange={(event) => setStrength(event.target.value)}><option>Conservative</option><option>Balanced</option><option>Strong</option></select></label>
              <label>Target length<select value={pages} onChange={(event) => setPages(event.target.value)}><option>1 page</option><option>2 pages</option><option>Best fit</option></select></label>
              <label>Renderer<select defaultValue="Reactive Resume"><option>Reactive Resume</option></select></label>
            </div>
            <div className="checkbox-row">
              <label><input type="checkbox" defaultChecked /> Reorder skills by relevance</label>
              <label><input type="checkbox" defaultChecked /> Select strongest projects</label>
              <label><input type="checkbox" defaultChecked /> Reject unsupported claims</label>
            </div>
          </section>

          <div className="action-row">
            <div className="readiness"><span className={bothValid ? 'ready-light' : 'ready-light off'} />{bothValid ? 'Inputs are ready for review' : 'Fix JSON issues before continuing'}</div>
            <button className="primary-button" disabled={!bothValid} onClick={reviewMapping}>Validate &amp; map fields <span>→</span></button>
          </div>
        </section>

        <aside className="contract-panel">
          <div className="contract-header"><p className="panel-label">Output contract</p><span>Draft</span></div>
          <div className="contract-score"><div className="score-ring"><strong>6</strong><span>sections</span></div><div><strong>What we will tailor</strong><p>Visible, reviewable and evidence-backed.</p></div></div>
          <ul className="section-list">
            {[
              ['Headline & summary', 'Rewrite'], ['Experience bullets', 'Rank'], ['Technical skills', 'Reorder'],
              ['Skill tags', 'Select'], ['Projects', 'Select'], ['Education', 'Preserve'],
            ].map(([name, action]) => <li key={name}><span className="check">✓</span><span>{name}<small>{action}</small></span></li>)}
          </ul>
          <div className="renderer-card"><span className="renderer-icon">R</span><div><strong>React PDF engine</strong><p>Local, client-side rendering</p></div><span className="recommended">Active</span></div>
          <div className="contract-footnote"><strong>No invented experience.</strong><p>Unmatched requirements will be flagged instead of fabricated.</p></div>
        </aside>
      </div>

      {reviewOpen && (
        <div className="modal-backdrop" role="presentation" onClick={() => setReviewOpen(false)}>
          <section className="review-modal" role="dialog" aria-modal="true" aria-labelledby="review-title" onClick={(event) => event.stopPropagation()}>
            <button className="close-button" aria-label="Close review" onClick={() => setReviewOpen(false)}>×</button>
            <p className="eyebrow accent">Deterministic mapping report</p><h2 id="review-title">Review before generating.</h2>
            <p>No content was invented or rewritten. Known fields were extracted and vacancy terms were used only to rank existing skills and projects.</p>
            <dl><div><dt>Mapped</dt><dd>{report?.mapped.length ?? 0} groups</dd></div><div><dt>Warnings</dt><dd>{report?.warnings.length ?? 0}</dd></div><div><dt>Renderer</dt><dd>Local React PDF</dd></div></dl>
            {report && <div className="mapping-report">
              <div><strong>Mapped successfully</strong><ul>{report.mapped.map((item) => <li key={item}>✓ {item}</li>)}</ul></div>
              <div><strong>Warnings</strong>{report.warnings.length ? <ul>{report.warnings.map((item) => <li key={item}>! {item}</li>)}</ul> : <p>No blocking warnings.</p>}</div>
              {!!report.ignored.length && <div><strong>Ignored top-level fields</strong><p>{report.ignored.join(', ')}</p></div>}
            </div>}
            <div className="modal-actions"><button className="text-button" onClick={downloadJson}>Download mapped JSON</button><button className="primary-button" disabled={!report || generating} onClick={generatePdf}>{generating ? 'Generating…' : 'Generate PDF'}</button></div>
          </section>
        </div>
      )}
    </main>
  );
}
