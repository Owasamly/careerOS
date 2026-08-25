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
    assert result.job.languages == ["English"]


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
