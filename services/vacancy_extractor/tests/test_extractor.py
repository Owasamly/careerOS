from vacancy_extractor import extract_vacancy
from vacancy_extractor.platforms import api_payload_to_html, ashby_to_html, personio_xml_to_html, plan_fetch


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


def test_ashby_plain_tasks_label_becomes_responsibilities() -> None:
    html = ashby_to_html(
        {
            "jobs": [{
                "title": "Working Student - Ecodesign",
                "jobUrl": "https://jobs.ashbyhq.com/example/job-id",
                "descriptionHtml": """
                    <p>Tasks</p>
                    <p>On a day-to-day basis, you'll be:</p>
                    <ul><li>Improving our internal LCA tools.</li><li>Supporting AI agent integration.</li></ul>
                    <p>Qualifications &amp; Background</p>
                    <ul><li>Good Python skills.</li><li>Currently enrolled at a university.</li></ul>
                """,
            }]
        },
        "example",
        "job-id",
    )

    result = extract_vacancy(html, "https://jobs.ashbyhq.com/example/job-id")

    assert result.job.responsibilities == [
        "On a day-to-day basis, you'll be:",
        "Improving our internal LCA tools.",
        "Supporting AI agent integration.",
    ]
    assert result.job.requirements == ["Good Python skills.", "Currently enrolled at a university."]


def test_ashby_doing_and_qualities_headings_are_normalized() -> None:
    html = """
        <main>
          <h1>IT Operations Working Student</h1>
          <h2>WHAT YOU'LL BE DOING</h2>
          <ul><li>Resolve day-to-day IT issues.</li><li>Manage user accounts.</li></ul>
          <h2>THE QUALITIES YOU'LL NEED FOR A SUCCESSFUL CAREER AT DATAGUARD</h2>
          <ul><li>You are currently studying IT.</li><li>You enjoy troubleshooting.</li></ul>
        </main>
    """

    result = extract_vacancy(html, "https://jobs.ashbyhq.com/dataguard/job-id")

    assert result.job.responsibilities == ["Resolve day-to-day IT issues.", "Manage user accounts."]
    assert result.job.requirements == ["You are currently studying IT.", "You enjoy troubleshooting."]


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


def test_eu_greenhouse_url_uses_api_and_decodes_rich_sections() -> None:
    plan = plan_fetch("https://job-boards.eu.greenhouse.io/isaraerospace/jobs/4931908101")
    assert plan.kind == "greenhouse_json"
    assert plan.fetch_url == "https://boards-api.greenhouse.io/v1/boards/isaraerospace/jobs/4931908101?content=true"
    html = api_payload_to_html(plan, {
        "title": "Working Student Computer Science",
        "company_name": "Isar Aerospace SE",
        "location": {"name": "Ottobrunn, Germany"},
        "content": "&lt;p&gt;&lt;strong&gt;Your Role in Our Space Mission:&lt;/strong&gt;&lt;/p&gt;&lt;ul&gt;&lt;li&gt;Implement software features&lt;/li&gt;&lt;/ul&gt;&lt;p&gt;&lt;strong&gt;Qualification Checklist&lt;/strong&gt;&lt;/p&gt;&lt;ul&gt;&lt;li&gt;Enrolled in Computer Science&lt;/li&gt;&lt;/ul&gt;",
    })
    result = extract_vacancy(html)
    assert result.job.company == "Isar Aerospace SE"
    assert result.job.responsibilities == ["Implement software features"]
    assert result.job.requirements == ["Enrolled in Computer Science"]
    assert result.extraction.status == "ready"


def test_json_ld_description_sections_are_parsed_for_join_style_pages() -> None:
    html = """
    <html><head><script type="application/ld+json">
    {
      "@context": "https://schema.org", "@type": "JobPosting",
      "title": "Founding AI Engineer",
      "hiringOrganization": {"name": "Alago"},
      "description": "&lt;h2&gt;Tasks&lt;/h2&gt;&lt;p&gt;Build production AI systems.&lt;/p&gt;&lt;h2&gt;Requirements&lt;/h2&gt;&lt;p&gt;Strong TypeScript and React skills.&lt;/p&gt;"
    }
    </script></head></html>
    """
    result = extract_vacancy(html, "https://join.com/companies/alagoai/example")
    assert result.job.responsibilities == ["Build production AI systems."]
    assert result.job.requirements == ["Strong TypeScript and React skills."]
    assert result.extraction.status == "ready"


def test_language_levels_and_required_flags_use_local_clause() -> None:
    html = """
    <main><h1>Engineer</h1><div class="company">Example</div>
      <h2>Tasks</h2><p>Build reliable systems.</p><p>Support customers.</p>
      <h2>Requirements</h2><p>We work in English. German helps for customer calls but isn't required. We have native speakers for that.</p>
    </main>
    """
    result = extract_vacancy(html)
    languages = {item.language: item for item in result.job.languages}
    assert languages["English"].level == "Not specified"
    assert languages["English"].required is True
    assert languages["German"].level == "Not specified"
    assert languages["German"].required is False


def test_styled_div_headlines_are_used_as_sections() -> None:
    html = """
    <main><h1>Working Student AI Engineering</h1><div class="company">appliedAI</div>
      <div class="content"><div class="headline display-2">Deine Aufgaben</div><div class="body prose"><p>Support AI engineering projects.</p><ul><li>Build Python workflows</li></ul></div></div>
      <div class="content"><div class="headline display-2">Dein Profil</div><div class="body prose"><ul><li>Currently enrolled in Computer Science</li><li>German and English proficiency</li></ul></div></div>
    </main>
    """
    result = extract_vacancy(html)
    assert result.job.responsibilities == ["Build Python workflows"]
    assert result.job.requirements == ["Currently enrolled in Computer Science", "German and English proficiency"]
    assert result.extraction.status == "ready"


def test_croz_personio_jobchat_uses_public_xml_prompts() -> None:
    plan = plan_fetch("https://crozdach.jobs.personio.de/job/2069751?language=de")
    assert plan.kind == "personio_xml"
    xml = """<?xml version="1.0"?><workzag-jobs><position><id>2069751</id><subcompany>CROZ DACH GmbH</subcompany><office>München</office><name>Working Student DevOps</name><jobDescriptions><jobDescription><name>Unser JobChat</name><value><![CDATA[Katy: Bei welchen Aufgaben genau könntest du Hilfe gebrauchen?<br>Berni: Bei verschiedenen Dingen! Recherchen zu Cloud-Anbietern und Testen von Tools. Außerdem Mitarbeit am DevOps-Lehrplan. Das wäre für Studierende super interessant.<br>Katy: Brauchen sie bestimmte Fähigkeiten oder Sprachkenntnisse?<br>Berni: Flüssiges Englisch ist ein Muss. Deutsch auf B1 ist ebenfalls erforderlich.]]></value></jobDescription></jobDescriptions></position></workzag-jobs>"""
    html = personio_xml_to_html(xml, plan)
    result = extract_vacancy(html)
    assert result.job.company == "CROZ DACH GmbH"
    assert result.job.responsibilities == ["Recherchen zu Cloud-Anbietern und Testen von Tools.", "Außerdem Mitarbeit am DevOps-Lehrplan."]
    assert result.job.requirements == ["Flüssiges Englisch ist ein Muss.", "Deutsch auf B1 ist ebenfalls erforderlich."]
    languages = {item.language: item for item in result.job.languages}
    assert languages["English"].level == "Fluent"
    assert languages["German"].level == "B1"
    assert result.extraction.status == "ready"
