# PDF REPORT GENERATION: Creates professional formatted PDFs for all reports (Job Seeker analysis, Recruiter decisions, Cover letters, Coaching progress) using ReportLab
"""
PDF Report Generator for Resume Analysis Results
Generates formatted PDF reports for different analysis modes and tools.
"""

from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY


def _is_meaningful_value(value):
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _append_text_lines(story, heading_style, normal_style, title, lines):
    cleaned_lines = [line for line in lines if _is_meaningful_value(line)]
    if not cleaned_lines:
        return False
    story.append(Paragraph(title, heading_style))
    for line in cleaned_lines:
        if isinstance(line, str):
            story.append(Paragraph(f"• {line}", normal_style))
        else:
            story.append(Paragraph(f"• {str(line)}", normal_style))
    story.append(Spacer(1, 0.15*inch))
    return True


def _append_generic_sections(story, heading_style, normal_style, result_data):
    rendered = False

    if _is_meaningful_value(result_data.get('headline')):
        rendered |= _append_text_lines(story, heading_style, normal_style, 'Headline', [result_data.get('headline')])

    about_value = result_data.get('about')
    if isinstance(about_value, dict):
        about_value = about_value.get('summary') or about_value.get('text') or about_value.get('about')
    if _is_meaningful_value(about_value):
        story.append(Paragraph('About', heading_style))
        story.append(Paragraph(str(about_value), normal_style))
        story.append(Spacer(1, 0.15*inch))
        rendered = True

    if _is_meaningful_value(result_data.get('experience_highlights')):
        highlights = result_data.get('experience_highlights')
        if isinstance(highlights, str):
            highlights = [line.strip(' -•\t') for line in highlights.splitlines() if line.strip(' -•\t')]
        elif not isinstance(highlights, (list, tuple, set)):
            highlights = [str(highlights)]
        rendered |= _append_text_lines(story, heading_style, normal_style, 'Experience Highlights', highlights)

    field_map = [
        ('rewritten_summary', 'Rewritten Summary'),
        ('estimated_salary_range', 'Estimated Salary Range'),
        ('market_trends', 'Market Trends'),
        ('current_level', 'Current Level'),
        ('summary', 'Summary'),
        ('generalFeedback', 'Summary'),
    ]

    for field_name, title in field_map:
        value = result_data.get(field_name)
        if _is_meaningful_value(value):
            story.append(Paragraph(title, heading_style))
            story.append(Paragraph(str(value), normal_style))
            story.append(Spacer(1, 0.15*inch))
            rendered = True

    list_fields = [
        ('negotiation_tips', 'Negotiation Tips'),
        ('skills_needed', 'Skills Needed'),
        ('recommendedRoles', 'Recommended Roles'),
        ('strengths', 'Strengths'),
        ('improvementAreas', 'Areas to Address'),
        ('skillGaps', 'Skill Gaps'),
    ]

    for field_name, title in list_fields:
        value = result_data.get(field_name)
        if isinstance(value, list) and value:
            story.append(Paragraph(title, heading_style))
            for item in value:
                if isinstance(item, dict):
                    text = item.get('skill') or item.get('title') or item.get('name') or item.get('summary') or item.get('reason') or item.get('description') or str(item)
                else:
                    text = str(item)
                story.append(Paragraph(f"• {text}", normal_style))
            story.append(Spacer(1, 0.15*inch))
            rendered = True

    return rendered


def _detect_job_seeker_report_title(result_data):
    if isinstance(result_data.get('headline'), str) or result_data.get('experience_highlights'):
        return 'LinkedIn Profile Report'
    if result_data.get('estimated_salary_range'):
        return 'Salary Estimation Report'
    if result_data.get('career_roadmap'):
        return 'Career Path Report'
    if result_data.get('score') is not None or result_data.get('checks'):
        return 'Resume Health Check Report'
    if result_data.get('rewritten_summary') or result_data.get('tailored_bullets'):
        return 'Resume Tailoring Report'
    if result_data.get('questions'):
        return 'Interview Questions Report'
    if result_data.get('skillGaps'):
        return 'Skill Gap Report'
    if result_data.get('coverLetter'):
        return 'Cover Letter Report'
    return 'Resume Analysis Report'


def generate_job_seeker_pdf(result_data):
    """
    Generate PDF report for Job Seeker analysis.
    
    Args:
        result_data: Analysis result dictionary
        
    Returns:
        BytesIO object containing PDF data
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1f2937'),
        spaceAfter=12,
        fontName='Helvetica-Bold'
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#374151'),
        spaceAfter=8,
        fontName='Helvetica-Bold',
        spaceBefore=8
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#4b5563'),
        alignment=TA_JUSTIFY,
        spaceAfter=6
    )
    
    story = []
    rendered_sections = False
    
    # Title
    story.append(Paragraph(f"📄 {_detect_job_seeker_report_title(result_data)}", title_style))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    
    # Match Scores
    if result_data.get('lexicalMatchPercentage') is not None:
        rendered_sections = True
        story.append(Paragraph("Match Scores", heading_style))
        
        scores_data = [
            ['Metric', 'Score'],
            ['Lexical Match', f"{result_data.get('lexicalMatchPercentage', 0):.1f}%"],
            ['Semantic Match', f"{result_data.get('semanticMatchPercentage', 0):.1f}%"],
            ['Combined Match', f"{result_data.get('combinedMatchPercentage', 0):.1f}%"],
        ]
        
        scores_table = Table(scores_data, colWidths=[3*inch, 2*inch])
        scores_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f3f4f6')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#d1d5db')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
        ]))
        story.append(scores_table)
        story.append(Spacer(1, 0.2*inch))
    
    # Strengths
    if result_data.get('strengths'):
        rendered_sections = True
        story.append(Paragraph("✅ Strengths", heading_style))
        for strength in result_data['strengths']:
            story.append(Paragraph(f"• {strength}", normal_style))
        story.append(Spacer(1, 0.15*inch))
    
    # Improvement Areas
    if result_data.get('improvementAreas'):
        rendered_sections = True
        story.append(Paragraph("📈 Areas for Improvement", heading_style))
        for area in result_data['improvementAreas']:
            story.append(Paragraph(f"• {area}", normal_style))
        story.append(Spacer(1, 0.15*inch))
    
    # Recommended Roles
    if result_data.get('recommendedRoles'):
        rendered_sections = True
        story.append(Paragraph("💼 Recommended Roles", heading_style))
        for role in result_data['recommendedRoles']:
            story.append(Paragraph(f"• {role}", normal_style))
        story.append(Spacer(1, 0.15*inch))
    
    # General Feedback
    if result_data.get('generalFeedback'):
        rendered_sections = True
        story.append(Paragraph("📝 General Feedback", heading_style))
        story.append(Paragraph(result_data['generalFeedback'], normal_style))
        story.append(Spacer(1, 0.15*inch))

    rendered_sections |= _append_generic_sections(story, heading_style, normal_style, result_data)

    if not rendered_sections:
        story.append(Paragraph("No structured analysis data was available.", normal_style))
        story.append(Spacer(1, 0.15*inch))
    
    # Skill Gaps
    if result_data.get('skillGaps'):
        story.append(PageBreak())
        story.append(Paragraph("⚠️ Skill Gaps", heading_style))
        for gap in result_data['skillGaps']:
            if isinstance(gap, dict):
                story.append(Paragraph(f"<b>{gap.get('skill', 'Unknown')}</b>: {gap.get('reason', '')}", normal_style))
            else:
                story.append(Paragraph(f"• {gap}", normal_style))
        story.append(Spacer(1, 0.15*inch))
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer


def generate_recruiter_pdf(result_data, candidate_name="Candidate"):
    """
    Generate PDF report for Recruiter analysis.
    
    Args:
        result_data: Analysis result dictionary
        candidate_name: Name of the candidate
        
    Returns:
        BytesIO object containing PDF data
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1f2937'),
        spaceAfter=12,
        fontName='Helvetica-Bold'
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#374151'),
        spaceAfter=8,
        fontName='Helvetica-Bold',
        spaceBefore=8
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#4b5563'),
        alignment=TA_JUSTIFY,
        spaceAfter=6
    )
    
    story = []
    rendered_sections = False
    
    # Title
    story.append(Paragraph(f"👔 Recruiter Analysis Report", title_style))
    story.append(Paragraph(f"Candidate: <b>{candidate_name}</b> | Generated: {datetime.now().strftime('%B %d, %Y')}", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    
    # Shortlist Dashboard
    if result_data.get('shortlistDashboard'):
        rendered_sections = True
        dashboard = result_data['shortlistDashboard']
        story.append(Paragraph("Decision Summary", heading_style))
        
        decision = dashboard.get('decision', 'PENDING')
        decision_colors = {
            'shortlisted': colors.HexColor('#10b981'),
            'review': colors.HexColor('#f59e0b'),
            'hold': colors.HexColor('#ef4444'),
            'PENDING': colors.HexColor('#6b7280')
        }
        
        decision_data = [
            ['Decision', f"{decision.upper()}"],
            ['Confidence', f"{dashboard.get('confidenceScore', 0):.0f}%"],
            ['Match Score', f"{dashboard.get('matchPercentage', 0):.1f}%"],
        ]
        
        decision_table = Table(decision_data, colWidths=[3*inch, 2*inch])
        decision_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f3f4f6')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#d1d5db')),
        ]))
        story.append(decision_table)
        story.append(Spacer(1, 0.2*inch))
        
        # Evidence
        if dashboard.get('evidence'):
            story.append(Paragraph("Why This Decision", heading_style))
            for evidence in dashboard['evidence']:
                if isinstance(evidence, dict):
                    title = evidence.get('title', 'Evidence')
                    desc = evidence.get('description', '')
                    story.append(Paragraph(f"<b>{title}:</b> {desc}", normal_style))
                else:
                    story.append(Paragraph(f"• {evidence}", normal_style))
            story.append(Spacer(1, 0.15*inch))
        
        # Risk Flags
        if dashboard.get('riskFlags'):
            story.append(Paragraph("⚠️ Risk Flags", heading_style))
            for flag in dashboard['riskFlags']:
                if isinstance(flag, dict):
                    severity = flag.get('severity', 'low').upper()
                    desc = flag.get('description', '')
                    severity_color = {'HIGH': '🔴', 'MEDIUM': '🟠', 'LOW': '🟡'}.get(severity, '⚪')
                    story.append(Paragraph(f"{severity_color} {desc}", normal_style))
                else:
                    story.append(Paragraph(f"• {flag}", normal_style))
            story.append(Spacer(1, 0.15*inch))
    
    # Match Scores
    if result_data.get('lexicalMatchPercentage') is not None:
        rendered_sections = True
        story.append(PageBreak())
        story.append(Paragraph("Match Analysis", heading_style))
        
        scores_data = [
            ['Metric', 'Score'],
            ['Lexical Match', f"{result_data.get('lexicalMatchPercentage', 0):.1f}%"],
            ['Semantic Match', f"{result_data.get('semanticMatchPercentage', 0):.1f}%"],
            ['Combined Match', f"{result_data.get('combinedMatchPercentage', 0):.1f}%"],
        ]
        
        scores_table = Table(scores_data, colWidths=[3*inch, 2*inch])
        scores_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f3f4f6')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#d1d5db')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
        ]))
        story.append(scores_table)
        story.append(Spacer(1, 0.2*inch))
    
    # Strengths
    if result_data.get('strengths'):
        rendered_sections = True
        story.append(Paragraph("✅ Key Strengths", heading_style))
        for strength in result_data['strengths']:
            story.append(Paragraph(f"• {strength}", normal_style))
        story.append(Spacer(1, 0.15*inch))
    
    # Improvement Areas
    if result_data.get('improvementAreas'):
        rendered_sections = True
        story.append(Paragraph("📈 Areas to Address", heading_style))
        for area in result_data['improvementAreas']:
            story.append(Paragraph(f"• {area}", normal_style))
        story.append(Spacer(1, 0.15*inch))
    
    # General Feedback
    if result_data.get('generalFeedback'):
        rendered_sections = True
        story.append(Paragraph("📝 Summary", heading_style))
        story.append(Paragraph(result_data['generalFeedback'], normal_style))
        story.append(Spacer(1, 0.15*inch))

    rendered_sections |= _append_generic_sections(story, heading_style, normal_style, result_data)

    if not rendered_sections:
        story.append(Paragraph("No structured recruiter analysis data was available.", normal_style))
        story.append(Spacer(1, 0.15*inch))
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer


def generate_cover_letter_pdf(cover_letter_text, candidate_name=""):
    """Generate PDF of cover letter."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=1*inch, bottomMargin=0.5*inch)
    
    styles = getSampleStyleSheet()
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.HexColor('#1f2937'),
        alignment=TA_LEFT,
        spaceAfter=12,
        leading=14
    )
    
    story = []
    
    # Date
    story.append(Paragraph(datetime.now().strftime('%B %d, %Y'), styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    # Cover Letter Content
    for line in cover_letter_text.split('\n'):
        if line.strip():
            story.append(Paragraph(line, normal_style))
        else:
            story.append(Spacer(1, 0.1*inch))
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer


def generate_coaching_report_pdf(coaching_data, mode='progress'):
    """
    Generate PDF for coaching reports (progress, study pack, etc.)
    
    Args:
        coaching_data: Coaching data dictionary
        mode: Type of coaching report ('progress', 'study_pack', 'interview')
        
    Returns:
        BytesIO object containing PDF data
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=22,
        textColor=colors.HexColor('#1f2937'),
        spaceAfter=12,
        fontName='Helvetica-Bold'
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#374151'),
        spaceAfter=8,
        fontName='Helvetica-Bold',
        spaceBefore=8
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#4b5563'),
        alignment=TA_JUSTIFY,
        spaceAfter=6
    )
    
    story = []
    
    # Title
    titles = {
        'progress': '📊 Coaching Progress Report',
        'study_pack': '📚 Study Pack Resources',
        'interview': '🎤 Interview Preparation'
    }
    story.append(Paragraph(titles.get(mode, 'Coaching Report'), title_style))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    
    # Progress Section
    if mode == 'progress' and coaching_data.get('overallProgress'):
        story.append(Paragraph("Overall Progress", heading_style))
        progress_data = [
            ['Category', 'Progress'],
            ['Overall', f"{coaching_data.get('overallProgress', 0)}%"],
        ]
        
        if coaching_data.get('categories'):
            for cat, val in coaching_data['categories'].items():
                progress_data.append([cat.title(), f"{val}%"])
        
        progress_table = Table(progress_data, colWidths=[3*inch, 2*inch])
        progress_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f3f4f6')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#d1d5db')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
        ]))
        story.append(progress_table)
        story.append(Spacer(1, 0.2*inch))
    
    # Study Pack Resources
    if mode == 'study_pack':
        if coaching_data.get('skillGaps'):
            story.append(Paragraph("Skill Gaps to Address", heading_style))
            for gap in coaching_data['skillGaps']:
                if isinstance(gap, dict):
                    story.append(Paragraph(f"<b>{gap.get('skill', '')}:</b> {gap.get('description', '')}", normal_style))
                else:
                    story.append(Paragraph(f"• {gap}", normal_style))
            story.append(Spacer(1, 0.15*inch))
        
        if coaching_data.get('studyPack'):
            story.append(PageBreak())
            story.append(Paragraph("Recommended Resources", heading_style))
            for resource in coaching_data['studyPack']:
                if isinstance(resource, dict):
                    title = resource.get('title', '')
                    desc = resource.get('description', '')
                    url = resource.get('url', '')
                    story.append(Paragraph(f"<b>{title}</b>: {desc}", normal_style))
                    if url:
                        story.append(Paragraph(f"<font color='blue'><u>{url}</u></font>", styles['Normal']))
                else:
                    story.append(Paragraph(f"• {resource}", normal_style))
                story.append(Spacer(1, 0.08*inch))
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer
