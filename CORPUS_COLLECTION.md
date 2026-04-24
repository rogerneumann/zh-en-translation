# Corpus Collection Guide

**Goal:** Collect 10,000-50,000 parallel Chinese-English manufacturing sentences
to enable fine-tuning and A/B testing of domain-specific translation quality.

---

## Why We Need a Corpus

Priority 3 (model fine-tuning) requires labeled training data.  The current
translation pipeline is general-purpose; a manufacturing corpus allows us to:

1. Measure translation quality before/after improvements (A/B testing)
2. Fine-tune the Argos zh->en model on domain-specific text
3. Use back-translation to generate additional synthetic training pairs

**Target:** 10k sentences for fine-tuning experiments, 50k for production-quality
model improvement.

---

## Data Format

Each entry is a single-line JSON object stored in `.jsonl` files
(one entry per line).  Required fields:

```json
{
  "source":   "patent/CN2024XXXXX",
  "chinese":  "镀锌钢板的表面处理工艺需要严格控制温度。",
  "english":  "The surface treatment process for galvanized steel sheets requires strict temperature control.",
  "domain":   "manufacturing",
  "verified": false
}
```

Optional fields:

```json
{
  "notes":      "Hot-dip galvanizing context",
  "source_url": "https://patents.google.com/patent/CN...",
  "added_at":   "2026-04-24T12:00:00+00:00"
}
```

Field definitions:

| Field | Required | Description |
|-------|----------|-------------|
| `source` | Yes | Short identifier: `"patent/CNXXXXXX"`, `"manual"`, `"standard/GB_T_5216"`, `"web"` |
| `chinese` | Yes | Simplified Chinese source text (traditional is accepted) |
| `english` | Yes | Reference English translation |
| `domain` | Yes | Domain tag: `"manufacturing"`, `"medical"`, `"legal"` |
| `verified` | Yes | `true` if reviewed by a subject-matter expert, `false` otherwise |
| `notes` | No | Context notes, variant translations, ambiguities |
| `source_url` | No | URL or citation for the original document |
| `added_at` | No | ISO 8601 timestamp |

---

## Source 1: Chinese Patent Database (Highest Volume)

Chinese patents are public, bilingual, and cover manufacturing in depth.
The English abstracts are human-translated by professional patent attorneys.

### CNIPA (China National Intellectual Property Administration)
- **URL:** https://pss-system.cponline.cnipa.gov.cn/
- **Search:** Use IPC codes for manufacturing:
  - B21 (Mechanical metal working without essentially removing material)
  - B22 (Casting; powder metallurgy)
  - B23 (Machine tools; metal working)
  - B24 (Grinding; polishing)
  - C21 (Metallurgy of iron)
  - C22 (Metallurgy; ferrous or non-ferrous alloys)
  - C23 (Coating metallic material; surface treatment)
- **Download format:** XML or full-text PDF
- **Quality:** High (professional translation); typical sentence pair count: 5-15 per patent abstract

### Google Patents (Easier Access)
- **URL:** https://patents.google.com/
- **Filter:** Language: zh, Assignee: Chinese manufacturers
- **Bilingual abstracts** available for patents with PCT applications
- **Bulk download:** Google Patents Public Data on BigQuery (license: CC BY 4.0)
  https://console.cloud.google.com/marketplace/product/google_patents_public_data/google-patents-public-data

### Extraction Steps
1. Download patent XML (CNIPA bulk download or Google Patents API)
2. Extract `<abstract>` sections in `zh` and `en`
3. Sentence-split each abstract (split on `。` for Chinese, `.` for English)
4. Align sentence pairs using BLEURT or LaBSE similarity scoring
5. Filter: keep pairs with similarity score > 0.75
6. Store in JSONL format with `source: "patent/CNXXXXXXXX"`

---

## Source 2: Manufacturing Standards (GB, ISO, DIN)

Official standards contain highly precise technical language.

### Chinese National Standards (GB/T)
- **URL:** https://openstd.samr.gov.cn/bzgk/gb/index
- **Relevant standards:**
  - GB/T 1184 - Geometric tolerances
  - GB/T 5216 - Alloy structural steels
  - GB/T 11351 - Bearing tolerances
  - GB/T 15115 - Die castings
  - GB/T 3077 - Alloy structural steels specification
- **Note:** Many GB standards are equivalently adopted from ISO; compare GB/T text with ISO for bilingual pairs

### ISO Standards with Chinese Translations
- **URL:** https://www.iso.org/standards.html
- Many ISO standards are sold with both English and Chinese text
- Check university library access (free for academic institutions)
- Key standard families: ISO 9001, ISO 1101, ISO 2768, ISO 286, ISO 965

### DIN Standards (German, but widely used in Chinese manufacturing)
- **URL:** https://www.din.de/en
- Search for Chinese translations published by SAC (Standardization Administration of China)
- Useful for automotive and precision manufacturing

### Extraction Notes
- Standards are copyrighted; use only sections explicitly licensed for reuse
  or ensure your usage qualifies as fair use / research exemption
- Prefer GB/T standards that are identical adoptions of ISO (e.g., "GB/T 19001-2016/ISO 9001:2015")
  because these provide exact bilingual equivalents

---

## Source 3: Technical Documentation (Manuals, Specs, Datasheets)

### Open-source Hardware Documentation
- **URL:** https://www.open-hardware.io/
- **GitHub:** Search `language:Chinese topic:manufacturing`
- Many hardware projects include bilingual Chinese/English documentation

### Product Manuals from Chinese OEMs
Sources that publicly release bilingual manuals:
- Hikvision (machine vision / industrial cameras): https://www.hikvision.com/en/support/download/
  - Products ship with bilingual Chinese-English manuals
- STEP Electric (servo drives): https://www.stepelectric.com/
- INOVANCE (industrial automation): https://en.inovance.com/support/document/

### Extraction Steps
1. Download bilingual PDF manual
2. Use a PDF parser (pdfplumber, PyPDF2) to extract text
3. Identify page-level language splits (many manuals interleave Chinese/English pages)
4. Align using sentence similarity (LaBSE embedding cosine similarity > 0.8)
5. Tag source as `"manual/PRODUCTNAME"`

---

## Source 4: Web Resources

### MDBG Chinese-English Dictionary Examples
- **URL:** https://www.mdbg.net/chinese/
- Contains usage examples for technical terms
- Free for non-commercial use; check terms of service before bulk scraping

### Chinese Technical Forums and Wiki
- **Baidu Baike (technical articles):** https://baike.baidu.com/
  - Many technical articles have English equivalents via Wikipedia cross-links
- **Wikipedia Chinese (zh.wikipedia.org):** 
  - Cross-link to English Wikipedia for bilingual sentence mining
  - Use WikiExtractor + sentence alignment

### CommaCai Parallel Corpus Tool
- **URL:** https://github.com/hpcaitech/ColossalAI (data pipelines)
- Various open parallel corpora contain manufacturing text

---

## Source 5: Community Contributions

### Contribution Guidelines

Anyone can add sentence pairs following this process:

1. **Fork** the repository
2. **Add** entries to `src/zh_en_translator/corpus/examples/manufacturing_samples.jsonl`
   or create a new JSONL file in `src/zh_en_translator/corpus/`
3. **Set** `"verified": false` unless you are a manufacturing domain expert
4. **Include** `"source"` so we can trace and verify the origin
5. **Submit** a pull request with a brief description of the source material

### Quality Standards
- Prefer complete sentences over fragments
- Use simplified Chinese unless the source document uses traditional
- Include domain-relevant technical terms (not just generic conversational text)
- Do not copy copyrighted material verbatim without license verification
- Flag uncertain translations with `"verified": false` and add a `"notes"` field

### Domain Expert Review
Entries marked `"verified": false` are candidates for expert review.
If you are a manufacturing engineer, translator, or domain expert:
- Review the `verified: false` entries in `manufacturing_samples.jsonl`
- Correct any translation errors in a new PR
- Change `"verified": true` when satisfied

---

## Alignment Tools

When extracting parallel text from bilingual documents, use sentence alignment:

### LaBSE (Language-agnostic BERT Sentence Embeddings)
```python
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('LaBSE')

zh_embeddings = model.encode(zh_sentences)
en_embeddings = model.encode(en_sentences)

from sklearn.metrics.pairwise import cosine_similarity
scores = cosine_similarity(zh_embeddings, en_embeddings)
# Keep pairs with score > 0.75
```

### LASER (Facebook Research)
```bash
pip install laserembeddings
python -m laserembeddings download-models
```

### BLEURT (Google)
- Use for post-hoc quality scoring of aligned pairs
- Score > 0.5 indicates reasonable translation quality

---

## Volume Estimates by Source

| Source | Expected Pairs | Quality | Effort |
|--------|---------------|---------|--------|
| CNIPA patents (IPC B21-B24, C21-C23) | 50k-200k | High | Medium |
| GB/T standards | 5k-20k | Very High | Low |
| OEM product manuals (10 products) | 2k-5k | High | Low |
| Wikipedia cross-links (manufacturing articles) | 3k-10k | Medium | Low |
| Community contributions | Ongoing | Varies | Ongoing |
| **Total (realistic 3 months)** | **60k-235k** | Mixed | Medium |

---

## Storage Layout

```
src/zh_en_translator/corpus/
    __init__.py
    corpus_manager.py           -- loading and iteration API
    examples/
        manufacturing_samples.jsonl   -- 20 hand-curated seed examples
        # Add domain-specific files here as collection grows:
        # manufacturing_patents.jsonl
        # manufacturing_standards.jsonl
        # manufacturing_manuals.jsonl
```

For large corpora (>10k entries), store outside the repo and load by path:

```python
from zh_en_translator.corpus import CorpusManager
mgr = CorpusManager()
mgr.load_file(Path("/data/zh-en-corpus/manufacturing_patents.jsonl"))
for entry in mgr.iter_entries(domain="manufacturing", verified_only=True):
    print(entry.chinese, "->", entry.english)
```

---

## Priority Collection Order

Given 3 months of part-time effort:

**Month 1:** Collect 2k-5k high-quality pairs
- Extract text from 5-10 bilingual OEM manuals (Hikvision, STEP, INOVANCE)
- Download and parse 50 relevant GB/T standards
- Target: 3k verified pairs

**Month 2:** Scale up via patents
- Set up CNIPA bulk download pipeline
- Align 500 manufacturing patents (IPC B23, C23)
- Target: 10k total (7k new from patents)

**Month 3:** Quality filtering + community launch
- Run LaBSE similarity filter on all patent pairs (keep top 70%)
- Launch community contribution guidelines
- Target: 15k-20k entries with 5k verified

---

## Legal Notes

- **Patents:** Patent texts are public domain after expiration; pending/active patents
  require care -- use only for research, not commercial deployment
- **Standards:** Most ISO/GB standards are copyrighted; extract only enough for
  research/testing (short excerpts); do not redistribute the full standard text
- **Manuals:** Check each manufacturer's documentation license; many allow
  redistribution for educational/research purposes
- **Wikipedia:** CC BY-SA 3.0 license; redistribution requires attribution and
  same license on derivative works

**When in doubt:** Set `"verified": false` and note the source URL so license
status can be verified later.
