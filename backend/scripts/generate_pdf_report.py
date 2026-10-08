import os
import sys
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def generate_pdf():
    pdf_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "DocuBrain_RAG_Evaluation_Report.pdf")
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=22,
        leading=26,
        textColor=colors.HexColor('#1E293B'),
        spaceAfter=6
    )

    subtitle_style = ParagraphStyle(
        'SubtitleStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=11,
        leading=14,
        textColor=colors.HexColor('#64748B'),
        spaceAfter=15
    )

    section_heading = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=colors.HexColor('#0F172A'),
        spaceBefore=12,
        spaceAfter=8
    )

    body_style = ParagraphStyle(
        'BodyStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor('#334155'),
        spaceAfter=6
    )

    bold_body_style = ParagraphStyle(
        'BoldBodyStyle',
        parent=body_style,
        fontName='Helvetica-Bold'
    )

    badge_pass = ParagraphStyle(
        'BadgePass',
        parent=body_style,
        fontName='Helvetica-Bold',
        textColor=colors.HexColor('#166534')
    )

    badge_fail = ParagraphStyle(
        'BadgeFail',
        parent=body_style,
        fontName='Helvetica-Bold',
        textColor=colors.HexColor('#991B1B')
    )

    elements = []

    # Title & Header
    elements.append(Paragraph("DocuBrain RAG Evaluation Report & Action Plan", title_style))
    elements.append(Paragraph("Fullstack RAG Benchmark Analysis • NovaCloud Evaluation Dataset (20 Questions)", subtitle_style))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#CBD5E1'), spaceAfter=15))

    # Executive Summary Box
    summary_data = [
        [
            Paragraph("<b>Total Questions</b>: 20", body_style),
            Paragraph("<b>Passed</b>: <font color='#166534'>15 (75.0%)</font>", body_style),
            Paragraph("<b>Failed</b>: <font color='#991B1B'>5 (25.0%)</font>", body_style),
            Paragraph("<b>LLM Engine</b>: Gemini 3.5/3.8 Flash", body_style)
        ]
    ]
    summary_table = Table(summary_data, colWidths=[130, 130, 130, 140])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#E2E8F0')),
        ('PADDING', (0,0), (-1,-1), 8),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 15))

    # Section 1: Completed Fixes (Action Plan 1)
    elements.append(Paragraph("1. Completed Fix: Model Endpoint Upgrade (Action Plan 1)", section_heading))
    p1 = (
        "<b>Status: COMPLETED</b><br/>"
        "We successfully updated all Gemini API model candidate lists across <code>llm_service.py</code>, "
        "<code>rag_agent.py</code>, <code>tools.py</code>, and <code>agentic_chunker.py</code> from deprecated models "
        "(<code>gemini-2.5-flash</code> / <code>gemini-2.0-flash</code> returning 404 errors) to active production models: "
        "<b>gemini-3.8-flash</b> and <b>gemini-3.5-flash</b>.<br/>"
        "<b>Result:</b> The RAG system now successfully connects to live Gemini APIs, enabling full generative "
        "synthesis and autonomous tool calling without 404 endpoint failures."
    )
    elements.append(Paragraph(p1, body_style))
    elements.append(Spacer(1, 10))

    # Section 2: Detailed Failed Questions Analysis
    elements.append(Paragraph("2. Detailed Analysis of 5 Failing Questions", section_heading))
    elements.append(Paragraph("The table below details why 5 out of 20 benchmark questions failed and the underlying root causes:", body_style))
    elements.append(Spacer(1, 6))

    failed_q_data = [
        [
            Paragraph("<b>ID & Category</b>", bold_body_style),
            Paragraph("<b>Question & Expected Answer</b>", bold_body_style),
            Paragraph("<b>Why it Failed (Root Cause)</b>", bold_body_style),
            Paragraph("<b>Action Required</b>", bold_body_style)
        ],
        [
            Paragraph("<b>Q8</b><br/>Conditional Reasoning", badge_fail),
            Paragraph("<b>Q:</b> If an application needs data to remain available after a regional failure, which NovaCloud capabilities help?<br/><b>Expected:</b> Cross-region replication (NovaObject/NovaDocument), availability zones, NovaSQL read replicas.", body_style),
            Paragraph("Retrieval searched for 'regional failure' and pulled Page 1 (Regional Architecture) instead of Page 9 (Disaster Recovery & Cross-Region Replication).", body_style),
            Paragraph("<b>Query Expansion / HyDE</b>: Expand conditional queries to include terms like 'disaster recovery', 'regional outage', and 'cross-region replication'.", body_style)
        ],
        [
            Paragraph("<b>Q9</b><br/>Timeline Retrieval", badge_fail),
            Paragraph("<b>Q:</b> When were Europe Central and Asia Pacific introduced?<br/><b>Expected:</b> Europe Central in 2021, Asia Pacific in 2023.", body_style),
            Paragraph("Fixed character chunking (600 chars) sliced the answer sentence in half across Chunk #4 boundary (cut at '...Europe Centra').", body_style),
            Paragraph("<b>Sentence-Aware Chunking</b>: Increase chunk size to 800–1000 chars and enforce sentence boundary splitting.", body_style)
        ],
        [
            Paragraph("<b>Q10</b><br/>Scenario Retrieval", badge_fail),
            Paragraph("<b>Q:</b> Temporary session storage that should not be only persistent copy?<br/><b>Expected:</b> NovaCache (Redis-compatible, in-memory).", body_style),
            Paragraph("Chunk #13 was truncated right before the warning: 'Customers should not use NovaCache as the only persistent storage mechanism...'", body_style),
            Paragraph("<b>Agentic / Semantic Chunking</b>: Group text into conceptual spans rather than fixed character limits.", body_style)
        ],
        [
            Paragraph("<b>Q15</b><br/>Distractor Test", badge_fail),
            Paragraph("<b>Q:</b> Does NovaCache provide persistent storage for critical data?<br/><b>Expected:</b> No, it is in-memory only.", body_style),
            Paragraph("Retrieval missed the negative assertion warning sentence because paragraph context was severed by standard chunking.", body_style),
            Paragraph("<b>Overlap & Negative Prompting</b>: Increase overlap to 150 chars and instruct LLM to explicitly assert 'No' on distractor queries.", body_style)
        ],
        [
            Paragraph("<b>Q18</b><br/>Precision / Contradiction", badge_fail),
            Paragraph("<b>Q:</b> Does NovaCloud automatically guarantee RPO of 15 min for all apps?<br/><b>Expected:</b> No, NovaCloud does not guarantee RPO/RTO for all services.", body_style),
            Paragraph("The section concluding sentence ('NovaCloud does not automatically guarantee...') was truncated at the end of Chunk #32.", body_style),
            Paragraph("<b>Chunk Overlap Increase</b>: Expand overlap from 80 to 150 chars to retain paragraph concluding sentences.", body_style)
        ]
    ]

    table = Table(failed_q_data, colWidths=[85, 175, 140, 130])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F1F5F9')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('PADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 15))

    # Section 3: Strategic Roadmap
    elements.append(Paragraph("3. Strategic Roadmap to Achieve 100% Pass Rate", section_heading))
    roadmap_items = [
        "<b>1. Implement Query Expansion / HyDE</b>: Intercept user queries with semantic synonyms before vector search to solve conditional reasoning misses (Q8).",
        "<b>2. Upgrade Chunking Strategy to Agentic / Semantic</b>: Replace fixed character splitting with <code>semantic_chunker_service</code> or <code>agentic_chunker_service</code> to prevent sentence fragmentation (Q9, Q10).",
        "<b>3. Expand Chunk Size & Overlap</b>: Increase <code>CHUNK_SIZE</code> from 600 to 900 characters and <code>CHUNK_OVERLAP</code> from 80 to 150 characters to capture concluding caveats (Q15, Q18).",
        "<b>4. Add API Quota Retry Backoff</b>: Add retry delays for batch evaluation scripts to prevent <code>429 RESOURCE_EXHAUSTED</code> quota limits on free-tier Gemini API keys."
    ]

    for item in roadmap_items:
        elements.append(Paragraph(f"• {item}", body_style))
        elements.append(Spacer(1, 3))

    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#CBD5E1'), spaceAfter=10))
    elements.append(Paragraph("Generated by DocuBrain Fullstack RAG System • Antigravity AI Engine", ParagraphStyle('Footer', parent=styles['Normal'], fontName='Helvetica-Oblique', fontSize=8, textColor=colors.HexColor('#94A3B8'), alignment=1)))

    doc.build(elements)
    print(f"PDF generated successfully at: {pdf_path}")

if __name__ == "__main__":
    generate_pdf()
