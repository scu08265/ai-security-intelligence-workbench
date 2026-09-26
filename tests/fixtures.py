"""Synthetic upstream payloads for collector tests.

Shapes are copied from the real APIs, but every value is invented.  Nothing
here should ever be presented as a real vulnerability.
"""

from __future__ import annotations

OSV_SYNTHETIC = {
    "id": "GHSA-synth-aaaa-bbbb",
    "aliases": ["CVE-2099-00001"],
    "summary": "Synthetic issue in a synthetic inference package",
    "details": "Synthetic fixture detail text. Not a real advisory.",
    "published": "2099-01-01T00:00:00Z",
    "modified": "2099-01-02T00:00:00Z",
    "severity": [{"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"}],
    "affected": [{
        "package": {"name": "vllm", "ecosystem": "PyPI"},
        "ranges": [{"type": "ECOSYSTEM", "events": [{"introduced": "0.8.3"}, {"fixed": "0.14.1"}]}],
    }],
    "references": [{"type": "WEB", "url": "https://example.invalid/synthetic"}],
    "database_specific": {"github_reviewed": True, "cwe_ids": ["CWE-122"]},
}

OSV_OPEN_ENDED_SYNTHETIC = {
    "id": "GHSA-synth-cccc-dddd",
    "aliases": ["CVE-2099-00002"],
    "summary": "Synthetic issue affecting all versions from a bound",
    "details": "Synthetic fixture.",
    "published": "2099-02-01T00:00:00Z",
    "modified": "2099-02-02T00:00:00Z",
    "severity": [],
    "affected": [{
        "package": {"name": "ollama", "ecosystem": "Go"},
        "ranges": [{"type": "ECOSYSTEM", "events": [{"introduced": "0"}, {"fixed": "0.17.1"}]}],
    }],
    "references": [],
    "database_specific": {},
}

OSV_GIT_RANGE_SYNTHETIC = {
    "id": "GHSA-synth-eeee-ffff",
    "aliases": [],
    "summary": "Synthetic issue expressed only as git commits",
    "details": "Synthetic fixture.",
    "published": "2099-03-01T00:00:00Z",
    "modified": "2099-03-02T00:00:00Z",
    "severity": [],
    "affected": [{
        "package": {"name": "langchain", "ecosystem": "PyPI"},
        "ranges": [{"type": "GIT", "events": [{"introduced": "deadbeef"}]}],
    }],
    "references": [],
    "database_specific": {},
}

OSV_QUERYBATCH_SYNTHETIC = {
    "results": [
        {"vulns": [{"id": "GHSA-synth-aaaa-bbbb", "modified": "2099-01-02T00:00:00Z"}]},
        {"vulns": []},
    ]
}

NVD_SYNTHETIC = {
    "vulnerabilities": [{
        "cve": {
            "id": "CVE-2099-00003",
            "sourceIdentifier": "synthetic@example.invalid",
            "published": "2099-04-01T00:00:00Z",
            "lastModified": "2099-04-02T00:00:00Z",
            "vulnStatus": "Analyzed",
            "descriptions": [{"lang": "en", "value": "Synthetic vLLM fixture used only for regression tests."}],
            "metrics": {"cvssMetricV31": [{
                "cvssData": {
                    "version": "3.1", "vectorString": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
                    "baseScore": 9.8, "baseSeverity": "CRITICAL",
                },
            }]},
            "weaknesses": [{"description": [{"lang": "en", "value": "CWE-122"}]}],
            "configurations": [{"nodes": [{"cpeMatch": [{
                "vulnerable": True,
                "criteria": "cpe:2.3:a:vllm:vllm:0.9.0:*:*:*:*:*:*:*",
                "versionStartIncluding": "0.8.3",
                "versionEndExcluding": "0.14.1",
            }]}]}],
            "references": [{"url": "https://example.invalid/nvd-synthetic"}],
        },
    }],
    "totalResults": 1,
    "resultsPerPage": 200,
    "startIndex": 0,
}

# `nvd_to_event` takes one entry; the collector iterates the wrapper.
NVD_ITEM_SYNTHETIC = NVD_SYNTHETIC["vulnerabilities"][0]

KEV_SYNTHETIC = {
    "catalogVersion": "2099.01.01",
    "dateReleased": "2099-01-01T00:00:00.0000Z",
    "vulnerabilities": [
        {
            "cveID": "CVE-2099-00004",
            "vendorProject": "Synthetic",
            "product": "MLflow",
            "vulnerabilityName": "Synthetic MLflow fixture",
            "dateAdded": "2099-01-01",
            "shortDescription": "Synthetic fixture entry; not a real exploitation record.",
            "requiredAction": "Synthetic action.",
            "dueDate": "2099-02-01",
            "knownRansomwareCampaignUse": "Unknown",
            "notes": "Synthetic.",
        },
        {
            "cveID": "CVE-2099-00005",
            "vendorProject": "Synthetic",
            "product": "Some Office Suite",
            "vulnerabilityName": "Unrelated synthetic fixture",
            "dateAdded": "2099-01-01",
            "shortDescription": "Synthetic fixture that must be filtered out as not AI-related.",
            "requiredAction": "Synthetic action.",
            "dueDate": "2099-02-01",
            "knownRansomwareCampaignUse": "Unknown",
            "notes": "",
        },
    ],
}

GHSA_SYNTHETIC = [{
    "ghsa_id": "GHSA-synth-gggg-hhhh",
    "cve_id": "CVE-2099-00006",
    "summary": "Synthetic Gradio fixture",
    "description": "Synthetic fixture description.",
    "severity": "high",
    "published_at": "2099-05-01T00:00:00Z",
    "updated_at": "2099-05-02T00:00:00Z",
    "withdrawn_at": None,
    "html_url": "https://github.com/advisories/GHSA-synth-gggg-hhhh",
    "cwe_ids": ["CWE-79"],
    "references": ["https://example.invalid/ghsa-synthetic"],
    "cvss": {"score": 7.5, "vector_string": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N"},
    "vulnerabilities": [{
        "package": {"name": "gradio", "ecosystem": "pip"},
        "vulnerable_version_range": "< 4.0.0",
        "first_patched_version": "4.0.0",
    }],
}]

RSS_SYNTHETIC = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>Synthetic Feed</title>
  <item>
    <title>Prompt injection in synthetic agents</title>
    <link>https://example.invalid/blog/prompt-injection</link>
    <guid>https://example.invalid/blog/prompt-injection</guid>
    <description>Synthetic fixture about prompt injection.</description>
    <pubDate>Wed, 01 Jan 2099 00:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Unrelated synthetic maintenance note</title>
    <link>https://example.invalid/blog/unrelated</link>
    <guid>https://example.invalid/blog/unrelated</guid>
    <description>Synthetic fixture with no AI content at all.</description>
    <pubDate>Wed, 01 Jan 2099 00:00:00 GMT</pubDate>
  </item>
</channel></rss>
"""

ARXIV_SYNTHETIC = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2099.00001v1</id>
    <title>Synthetic study of large language model security</title>
    <summary>Synthetic abstract about large language model security.</summary>
    <published>2099-06-01T00:00:00Z</published>
    <category term="cs.CR"/>
    <primary_category xmlns="http://arxiv.org/schemas/atom" term="cs.CR"/>
  </entry>
</feed>
"""

OPENALEX_SYNTHETIC = {
    "meta": {"count": 2},
    "results": [
        {
            "id": "https://openalex.org/W2099000001",
            "display_name": "Synthetic study of prompt injection in large language models",
            "publication_date": "2099-06-01",
            "doi": "https://doi.org/10.0000/synthetic-ai-security",
            "primary_location": {
                "landing_page_url": "https://example.invalid/openalex/ai-security",
                "pdf_url": "https://example.invalid/openalex/ai-security.pdf",
            },
            "best_oa_location": {
                "landing_page_url": "https://example.invalid/openalex/ai-security",
                "pdf_url": "https://example.invalid/openalex/ai-security.pdf",
            },
            "abstract_inverted_index": {
                "Synthetic": [0], "study": [1], "about": [2],
                "prompt": [3], "injection": [4], "and": [5],
                "large": [6], "language": [7], "model": [8], "security": [9],
            },
            "primary_topic": {"display_name": "Language model security"},
            "topics": [{"display_name": "Language model security"}],
        },
        {
            "id": "https://openalex.org/W2099000002",
            "display_name": "Unrelated synthetic food science paper",
            "publication_date": "2099-06-01",
            "abstract_inverted_index": {"Food": [0], "storage": [1], "temperature": [2]},
            "topics": [{"display_name": "Food preservation"}],
        },
    ],
}

HTML_SYNTHETIC = """<html><head><title>Synthetic Standard Page</title></head>
<body><script>ignored()</script><h1>Prompt injection</h1>
<p>Synthetic standard text about prompt injection.</p></body></html>"""
