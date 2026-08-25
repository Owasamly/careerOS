from vacancy_extractor import extract_vacancy


def test_extracts_jobposting_json_ld() -> None:
    html = """
    <html><head><script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "JobPosting",
      "title": "Cloud Security Engineer",
      "hiringOrganization": {"@type": "Organization", "name": "Example GmbH"},
      "jobLocation": {"address": {"addressLocality": "Munich", "addressCountry": "DE"}},
      "employmentType": "FULL_TIME",
      "description": "Secure AWS infrastructure using IAM, Python, Terraform and incident response.",
      "qualifications": ["AWS experience", "Python scripting", "Professional English"],
      "responsibilities": ["Review IAM policies", "Automate security checks"]
    }
    </script></head></html>
    """
    result = extract_vacancy(html, "https://jobs.example.com/123")
    assert result.extraction.method == "json_ld"
    assert result.job.title == "Cloud Security Engineer"
    assert result.job.company == "Example GmbH"
    assert result.job.requirements == ["AWS experience", "Python scripting", "Professional English"]
    assert {"AWS", "IAM", "Python", "Terraform", "Incident Response"}.issubset(result.job.skills)
    assert result.job.languages[0].language == "English"
    assert result.job.languages[0].level == "Professional"


def test_falls_back_to_visible_sections() -> None:
    html = """
    <html><head><title>Security Analyst</title></head><body><main>
      <h1>Security Analyst</h1><div class="company-name">Blue Team GmbH</div>
      <div class="job-location">Berlin</div><p>Help protect our Linux environment.</p>
      <h2>Your tasks</h2><ul><li>Investigate SIEM alerts</li></ul>
      <h2>Requirements</h2><ul><li>Linux experience</li><li>Incident response knowledge</li></ul>
      <h2>Nice to have</h2><ul><li>Python scripting</li></ul>
    </main></body></html>
    """
    result = extract_vacancy(html)
    assert result.extraction.method == "html_heuristic"
    assert result.job.company == "Blue Team GmbH"
    assert result.job.responsibilities == ["Investigate SIEM alerts"]
    assert result.job.requirements == ["Linux experience", "Incident response knowledge"]
    assert result.job.nice_to_haves == ["Python scripting"]


def test_derives_personio_company_and_automation_stack() -> None:
    html = """
    <html><body><main><h1>Working Student AI Automation</h1>
    <p>Build workflows using AI, Microsoft 365, Power Automate and n8n.</p>
    <h2>Requirements</h2><ul><li>Strong Excel skills</li></ul>
    </main></body></html>
    """
    result = extract_vacancy(html, "https://unternehmertum.jobs.personio.de/job/2707777")
    assert result.job.company == "Unternehmertum"
    assert {"AI", "Microsoft 365", "Power Automate", "N8N", "Excel"}.issubset(result.job.skills)


def test_extracts_german_sections_languages_and_contact() -> None:
    html = """
    <html><body><main><h1>Cloud Security Engineer</h1>
      <h2>Deine Aufgaben</h2><ul><li>Du sicherst unsere AWS Umgebung.</li></ul>
      <h2>Das bringst du mit</h2><ul>
        <li>Verhandlungssichere Deutschkenntnisse auf C1-Niveau</li>
        <li>Fließendes Englisch</li>
      </ul>
      <section class="contact"><h2>Dein Kontakt</h2><h3>Anna Beispiel</h3>
        <p>Talent Acquisition Manager</p>
        <a href="mailto:anna@example.com">anna@example.com</a>
        <a href="tel:+4989123456">+49 89 123456</a>
      </section>
    </main></body></html>
    """
    result = extract_vacancy(html, "https://example.jobs/personio")
    assert result.job.responsibilities == ["Du sicherst unsere AWS Umgebung."]
    assert len(result.job.requirements) == 2
    assert [(item.language, item.level) for item in result.job.languages] == [("German", "C1"), ("English", "Fluent")]
    assert result.job.contact is not None
    assert result.job.contact.name == "Anna Beispiel"
    assert result.job.contact.role == "Talent Acquisition Manager"
    assert result.job.contact.email == "anna@example.com"
    assert result.job.contact.phone == "+4989123456"
