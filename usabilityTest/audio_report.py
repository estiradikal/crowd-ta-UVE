"""Generación de informes de audio en PDF."""
from collections import Counter
from io import BytesIO
import math
from xml.sax.saxutils import escape

def number(value):
    try:
        value = float(value)
        return max(0, value) if math.isfinite(value) else 0
    except (TypeError, ValueError):
        return 0

def clock(value):
    seconds = int(number(value))
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    return f'{hours:02d}:{minutes:02d}:{seconds:02d}' if hours else f'{minutes:02d}:{seconds:02d}'

def event_description(event):
    kind = str(event.get('type', ''))
    if kind == 'silence_warning':
        return 'Aviso por ausencia de voz'
    if kind == 'audio_warning':
        return 'Canto probable' if 'CANTO' in str(event.get('label', '')).upper() else 'Música probable'
    if kind in {'vad_error', 'vad_recovery', 'vad_status_save_error', 'music_monitor_error'}:
        return {
            'vad_error': 'Error al iniciar el detector de voz',
            'vad_recovery': 'Recuperación del detector de voz',
            'vad_status_save_error': 'Error al guardar el estado de la tarea',
            'music_monitor_error': 'Error del análisis musical',
        }[kind]
    return None

def build_audio_report(records, *, title='Informe de audio', demo=False):
    from datetime import timezone, timedelta
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, KeepTogether

    records = list(records)
    if not records:
        raise ValueError('No hay registros de audio para este informe.')
    output = BytesIO()
    navy = colors.HexColor('#17385a')
    styles = getSampleStyleSheet()
    for name, size, leading, extra in [
        ('ReportTitle', 20, 24, dict(fontName='Helvetica-Bold', textColor=navy, spaceAfter=12)),
        ('SectionTitle', 11, 15, dict(fontName='Helvetica-Bold', textColor=navy, spaceBefore=11, spaceAfter=7, keepWithNext=True)),
        ('ReportBody', 9, 13, dict(spaceAfter=6)),
        ('Cell', 9, 12, {}),
        ('HeadCell', 9, 12, dict(fontName='Helvetica-Bold', textColor=colors.white)),
        ('ReportNote', 8, 11, dict(textColor=colors.HexColor('#526171'), spaceAfter=5)),
    ]:
        styles.add(ParagraphStyle(name=name, fontSize=size, leading=leading, **extra))

    def p(value, style='ReportBody'):
        return Paragraph(escape(str(value)), styles[style])

    def date(value, zone):
        if value is None:
            return 'No registrado'
        # Django guarda los instantes con zona; los valores antiguos sin zona se interpretan en UTC.
        aware = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
        return aware.astimezone(zone).strftime('%d/%m/%Y %H:%M:%S')

    def percent(value, denominator):
        return f'{100 * number(value) / denominator:.1f} %' if denominator else 'Sin datos'

    def table(headers, rows, widths):
        result = Table([[p(c, 'HeadCell') for c in headers]] +
                       [[p(c, 'Cell') for c in row] for row in rows],
                       colWidths=widths, repeatRows=1, hAlign='LEFT')
        result.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), navy),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f0f5f8'), colors.white]),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
            ('TOPPADDING', (0, 0), (-1, -1), 7),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]))
        return result

    flow = [p('CrowdTA', 'ReportNote'), p(title, 'ReportTitle')]
    if demo:
        flow.append(p('EJEMPLO CON DATOS FICTICIOS', 'ReportNote'))
    for index, r in enumerate(records, 1):
        analyzed = sum(number(v) for v in [r.speech_seconds, r.silence_seconds, r.noise_seconds])
        voice = percent(r.speech_seconds, analyzed)
        vad_alerts = int(number(r.vad_alerts))
        music_alerts = int(number(r.music_alerts) + number(r.singing_alerts))
        events = [e for e in r.events if isinstance(e, dict)] if isinstance(r.events, list) else []
        types = Counter(str(e.get('type', '')) for e in events)
        zone_name = getattr(r, 'client_timezone', '') or ''
        offset = getattr(r, 'client_utc_offset_minutes', None)
        zone = None
        if zone_name:
            try:
                from zoneinfo import ZoneInfo
                zone = ZoneInfo(zone_name)
            except (KeyError, ValueError):
                pass
        if zone is not None:
            zone_label = f'Zona horaria del dispositivo al iniciar: {zone_name}.'
        elif offset is not None:
            # JavaScript expresa minutos de UTC menos hora local.
            zone = timezone(timedelta(minutes=-int(offset)))
            sign = '+' if offset <= 0 else '-'
            hours, minutes = divmod(abs(int(offset)), 60)
            zone_label = f'Hora del dispositivo al iniciar: UTC{sign}{hours:02d}:{minutes:02d}.'
        else:
            zone = timezone.utc
            zone_label = 'Zona del dispositivo no registrada; fechas mostradas en UTC.'
        intro = []
        if len(records) > 1:
            intro.append(p(f'Registro {index} - Tarea {r.task_id}', 'SectionTitle'))
        intro.extend([
            p(f'Participante: {r.subject_id}'),
            p(f'Tarea: {r.task_id} | Estado: {"Finalizado" if r.finalized else "Parcial; cierre no confirmado"}'),
            p(f'Inicio: {date(r.created_at, zone)} | Cierre: {date(r.completed_at, zone)}', 'ReportNote'),
            p(zone_label + ' Duraciones expresadas en min:seg.', 'ReportNote'),
        ])
        flow.append(KeepTogether(intro))
        flow.append(p('Resumen del análisis', 'SectionTitle'))
        flow.append(p(f'Duración registrada: {clock(r.duration_seconds)} | Tiempo clasificado: {clock(analyzed)}'))
        flow.append(table(['Clasificación', 'Tiempo', 'Porcentaje'], [
            ['Voz detectada', clock(r.speech_seconds), voice],
            ['Silencio estimado', clock(r.silence_seconds), percent(r.silence_seconds, analyzed)],
            ['Sonidos no verbales', clock(r.noise_seconds), percent(r.noise_seconds, analyzed)],
        ], [88*mm,43*mm,43*mm]))
        flow.append(p('Los porcentajes usan el tiempo clasificado. La duración registrada puede incluir el inicio o cierre del monitor.', 'ReportNote'))
        flow.append(p('Alertas', 'SectionTitle'))
        flow.append(table(['Indicador', 'Resultado'], [
            ['Avisos por ausencia de voz', vad_alerts],
            ['Alertas de música o canto probable', music_alerts],
            ['Mayor intervalo seguido sin voz detectada', clock(r.longest_silence_seconds)],
        ], [131*mm,43*mm]))
        flow.append(p('Observación automática', 'SectionTitle'))
        if analyzed:
            flow.append(p(f'Se detectó voz durante el {voice} del tiempo clasificado. Se registraron '
                          f'{vad_alerts} aviso(s) por ausencia de voz y {music_alerts} alerta(s) de música o canto probable.'))
        else:
            flow.append(p('No hay tiempo clasificado disponible para calcular porcentajes.'))
        flow.append(p('Momentos para revisar', 'SectionTitle'))
        selected = sorted(((number(e.get('at_seconds')), event_description(e)) for e in events
                           if event_description(e)), key=lambda value: value[0])
        if selected:
            flow.append(table(['Tiempo', 'Evento'], [[clock(t), desc] for t,desc in selected], [34*mm,140*mm]))
        else:
            flow.append(p('No se registraron alertas ni errores en el historial disponible.'))
        if not r.finalized:
            flow.append(p('Datos parciales: los tiempos pueden no haberse actualizado antes del cierre de la página.', 'ReportNote'))
        if len(events) >= 250 or not types['session_started']:
            flow.append(p('El historial de eventos puede estar incompleto; se conservan como máximo los últimos 250 eventos.', 'ReportNote'))
        if not types['vad_ready']:
            flow.append(p('El historial disponible no permite confirmar el inicio correcto del detector de voz.', 'ReportNote'))
        if analyzed > number(r.duration_seconds):
            flow.append(p('Revisar consistencia: el tiempo clasificado supera la duración registrada.', 'ReportNote'))
        if types['vad_error'] or types['music_monitor_error'] or types['vad_status_save_error']:
            flow.append(p('Se registraron errores técnicos; revisar su efecto en la grabación y los resultados.', 'ReportNote'))
        flow.append(p(f'Referencia del análisis: {r.session_id}', 'ReportNote'))

    flow.append(KeepTogether([
        p('Cómo interpretar estos resultados', 'SectionTitle'),
        p('Son estimaciones automáticas que apoyan la revisión de la grabación; no determinan si la tarea se realizó correctamente. '
          'Cero alertas no demuestra ausencia de música. Las alertas de música o canto no indican su duración exacta. '
          'Los eventos se cuentan desde el inicio del monitor y pueden tener un desfase respecto al video.', 'ReportNote'),
    ]))

    def footer(canvas, doc):
        canvas.saveState()
        width, _ = A4
        canvas.setStrokeColor(colors.HexColor('#d9e3eb'))
        canvas.line(18*mm, 17*mm, width-18*mm, 17*mm)
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(navy)
        canvas.drawString(18*mm, 12*mm, 'CrowdTA | Análisis automático de audio')
        canvas.drawRightString(width-18*mm, 12*mm, f'Página {doc.page}')
        canvas.restoreState()
    SimpleDocTemplate(output, pagesize=A4, rightMargin=18*mm, leftMargin=18*mm,
                      topMargin=17*mm, bottomMargin=23*mm, title=title, author='CrowdTA').build(
                          flow, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
