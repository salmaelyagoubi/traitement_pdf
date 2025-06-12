
from flask import Flask, request, send_file, make_response, jsonify
from datetime import datetime, time
import pdfplumber
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import tempfile
import os
import io
import re

app = Flask(__name__)

@app.route('/traiter', methods=['POST'])
def traiter_pdf():
    file = request.files['file']

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, "input.pdf")
        output_path = os.path.join(tmpdir, "modified.pdf")
        file.save(input_path)

        try:
            with pdfplumber.open(input_path) as pdf:
                lines = []
                for page in pdf.pages:
                    if page.extract_text():
                        lines.extend(page.extract_text().splitlines())

            # === Extraction nom complet + ID ===
            full_name = ""
            person_id = ""
            for line in lines:
                match = re.search(r"Mr\s+([A-Z]+ [A-Za-zÀ-ÿ\-']+)\s+\((E\d+)\)", line)
                if match:
                    full_name = match[1].strip()
                    person_id = match[2].strip()
                    break
            # === EXTRAIRE LA DATE DE MISSION ===
            mission_date = ""
            for line in lines:
                match = re.search(r'Fiche de missions du (\d{2}/\d{2}/\d{4})', line)
                if match:
                    mission_date = match.group(1)
                    break

            # === Heure de début ===
            first_start = None
            for line in lines:
                if "Heure de début de mission" in line:
                    match = re.search(r'\b(\d{1,2})[:h](\d{2})\b', line)
                    if match:
                        first_start = datetime.strptime(f"{match[1]}:{match[2]}", "%H:%M")
                        break
            if not first_start:
                return "Heure de début non trouvée", 400

            # === Heure de fin ===
            all_times = []
            for line in lines:
                found = re.findall(r'\b(\d{1,2})[:h](\d{2})\b', line)
                for h, m in found:
                    all_times.append(datetime.strptime(f"{h}:{m}", "%H:%M"))

            valid_times = [t for t in all_times if t >= first_start]
            if not valid_times:
                return "Aucune heure de fin trouvée", 400

            last_time = max(valid_times)
            duration = last_time - first_start
            total_minutes = duration.total_seconds() / 60
            hours = int(total_minutes // 60)
            minutes = int(total_minutes % 60)

            start_str = first_start.strftime("%H:%M")
            end_str = last_time.strftime("%H:%M")
            duration_str = f"{hours}h{minutes:02d}"

            # === Déterminer les AVANTAGES ===
            # Define precise time ranges
            petit_dej_range = (time(3, 0), time(10, 0))
            dej_range = (time(11, 50), time(14, 0))
            diner_range = (time(18, 50), time(23, 59))

            def is_in_range(t, r):
                return r[0] <= t <= r[1]

            start_time = first_start.time()
            end_time = last_time.time()

            avantages = []
            if is_in_range(start_time, petit_dej_range) or is_in_range(end_time, petit_dej_range):
                avantages.append("Petit déjeuner")
            if is_in_range(start_time, dej_range) or is_in_range(end_time, dej_range):
                avantages.append("Déjeuner")
            if is_in_range(start_time, diner_range) or is_in_range(end_time, diner_range):
                avantages.append("Dîner")

            avantage_str = ", ".join(avantages) if avantages else "Aucun"


            # === Texte final à insérer ===
            message = (
                f"Heure de fin : {end_str}\n"
                f"Heure de début : {start_str}\n"
                f"Durée totale de la mission : {duration_str}\n"
                f"Avantages attribués : {avantage_str}"
            )

            packet = io.BytesIO()
            can = canvas.Canvas(packet, pagesize=A4)
            can.setFont("Helvetica-Bold", 11)
            y = 100
            for line in message.split("\n"):
                can.drawString(50, y, line)
                y += 15
            can.save()
            packet.seek(0)

            original = PdfReader(input_path)
            overlay = PdfReader(packet)
            writer = PdfWriter()
            for i, page in enumerate(original.pages):
                if i == len(original.pages) - 1:
                    page.merge_page(overlay.pages[0])
                writer.add_page(page)

            with open(output_path, "wb") as f:
                writer.write(f)

            with open(output_path, "rb") as f:
                file_data = f.read()

                response = make_response(file_data)
                response.headers.set("Content-Type", "application/pdf; charset=utf-8")
                response.headers.set("Content-Disposition", "attachment", filename="pdf_modifie.pdf")
                response.headers.set("x-id", person_id)
                response.headers.set("x-nom", full_name)
                response.headers.set("x-duree", duration_str)
                response.headers.set("x-avantages", ", ".join(avantages))
                response.headers.set("x-date", mission_date)
            return response

        except Exception as e:
            return f"Erreur pendant le traitement : {str(e)}", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
