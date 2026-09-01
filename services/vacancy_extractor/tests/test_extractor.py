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
    assert result.extraction.status == "ready"
    assert result.extraction.can_generate_cv is True


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
    assert result.job.responsibilities == ["Ship safely"]


def test_ashby_strong_paragraph_labels_become_sections() -> None:
    plan = plan_fetch("https://jobs.ashbyhq.com/Dataleap/664cee48-f04c-494a-9820-33681fc77999")
    html = api_payload_to_html(plan, {"jobs": [{
        "id": "664cee48-f04c-494a-9820-33681fc77999",
        "title": "Working Student Integrations",
        "jobUrl": "https://jobs.ashbyhq.com/Dataleap/664cee48-f04c-494a-9820-33681fc77999",
        "descriptionHtml": "<p><strong>What You’ll Do</strong></p><ul><li>Build integrations</li></ul><p><strong>You’re a Fit If</strong></p><ul><li>Python and TypeScript</li></ul>",
    }]})
    result = extract_vacancy(html)
    assert result.job.responsibilities == ["Build integrations"]
    assert result.job.requirements == ["Python and TypeScript"]
    assert result.extraction.status == "ready"


def test_celonis_dynamic_job_url_uses_public_api_payload() -> None:
    plan = plan_fetch("https://careers.celonis.com/join-us/open-positions/job-detail?jobId=7885744003")
    assert plan.fetch_url == "https://dxp-api.celonis.com/v1/jobs/7885744003"
    html = api_payload_to_html(plan, {
        "title": "Working Student Corporate Law",
        "groupedLocation": "Munich, Germany",
        "description": "&lt;p&gt;&lt;strong&gt;The work you’ll do:&lt;/strong&gt;&lt;/p&gt;&lt;ul&gt;&lt;li&gt;Conduct legal research&lt;/li&gt;&lt;/ul&gt;&lt;p&gt;&lt;strong&gt;The qualifications you need:&lt;/strong&gt;&lt;/p&gt;&lt;ul&gt;&lt;li&gt;Enrolled in a law program&lt;/li&gt;&lt;/ul&gt;",
    })
    result = extract_vacancy(html, "https://careers.celonis.com/join-us/open-positions/job-detail?jobId=7885744003")
    assert result.job.company == "Celonis"
    assert result.job.responsibilities == ["Conduct legal research"]
    assert result.job.requirements == ["Enrolled in a law program"]
    assert result.extraction.status == "ready"


def test_blocks_application_form_without_job_sections() -> None:
    html = """
    <html><head><title>Apply</title></head><body><main><h1>Apply for this job</h1>
      <p>Please enter your personal details below.</p>
      <input><input><input><input><input><textarea></textarea>
    </main></body></html>
    """
    result = extract_vacancy(html)
    assert result.extraction.status == "failed"
    assert result.extraction.can_generate_cv is False
    assert any("application form" in item for item in result.extraction.blockers)


def test_blocks_access_challenge_page() -> None:
    result = extract_vacancy("<html><head><title>Just a moment</title></head><body><h1>Verify you are human</h1></body></html>")
    assert result.extraction.status == "failed"
    assert result.extraction.can_generate_cv is False
    assert result.extraction.field_confidence["requirements"] == 0


def test_does_not_treat_ordinary_make_as_automation_tool() -> None:
    html = """
    <main><h1>Legal Working Student</h1><div class="company">Example</div>
      <p>Help us make processes work for people and companies.</p>
      <h2>The work you'll do</h2><ul><li>Conduct legal research and make recommendations.</li></ul>
      <h2>The qualifications you need</h2><ul><li>Currently enrolled in law.</li><li>Excellent research skills.</li></ul>
    </main>
    """
    result = extract_vacancy(html)
    assert "Make" not in result.job.skills
