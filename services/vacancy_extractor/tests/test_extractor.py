from vacancy_extractor import extract_vacancy
from vacancy_extractor.platforms import api_payload_to_html, plan_fetch


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


def test_personio_apply_url_is_normalized_and_mission_is_extracted() -> None:
    plan = plan_fetch("https://example.jobs.personio.de/job/123/apply?language=de")
    assert plan.platform == "personio"
    assert plan.fetch_url == "https://example.jobs.personio.de/job/123?language=de"
    result = extract_vacancy("<main><h1>Engineer</h1><h2>Your mission</h2><ul><li>Build secure systems</li></ul><h2>Your profile</h2><ul><li>Python</li></ul></main>")
    assert result.job.responsibilities == ["Build secure systems"]
    assert result.job.requirements == ["Python"]


def test_lever_api_payload_keeps_named_sections() -> None:
    plan = plan_fetch("https://jobs.lever.co/acme/abc-123")
    html = api_payload_to_html(plan, {
        "text": "Security Engineer",
        "categories": {"location": "Berlin"},
        "description": "<p>Protect our platform.</p>",
        "lists": [
            {"text": "Responsibilities", "content": "<ul><li>Investigate alerts</li></ul>"},
            {"text": "Requirements", "content": "<ul><li>Python experience</li></ul>"},
        ],
    })
    result = extract_vacancy(html)
    assert result.job.responsibilities == ["Investigate alerts"]
    assert result.job.requirements == ["Python experience"]


def test_ashby_api_payload_selects_requested_job() -> None:
    plan = plan_fetch("https://jobs.ashbyhq.com/acme/job-2")
    html = api_payload_to_html(plan, {"jobs": [
        {"title": "Wrong", "jobUrl": "https://jobs.ashbyhq.com/acme/job-1", "descriptionHtml": ""},
        {"title": "Right", "jobUrl": "https://jobs.ashbyhq.com/acme/job-2", "location": "Remote", "descriptionHtml": "<h2>What you'll do</h2><ul><li>Ship safely</li></ul><h2>Requirements</h2><ul><li>Linux</li></ul>"},
    ]})
    result = extract_vacancy(html)
    assert result.job.title == "Right"
    assert result.job.requirements == ["Linux"]
