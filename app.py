from flask import Flask, request, send_file, make_response, jsonify
from datetime import datetime
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

    # Création d’un fichier temporaire
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, "input.pdf")
        output_path = os.path.join(tmpdir, "modified.pdf")
        file.save(input_path)

        # Traitement du PDF (ta logique ici ⬇)
        try:
            with pdfplumber.open(input_path) as pdf:
                lines = []
                for page in pdf.pages:
                    if page.extract_text():
                        lines.extend(pdf.pages[pdf.pages.index(page)].extract_text().splitlines())

            # Heure de début
            first_start = None
            for line in lines:
                if "Heure de début de mission" in line:
                    match = re.search(r'\b(\d{1,2})[:h](\d{2})\b', line)
                    if match:
                        first_start = datetime.strptime(f"{match[1]}:{match[2]}", "%H:%M")
                        break
            if not first_start:
                return "Heure de début non trouvée", 400

            # Heure de fin
            all_times = []
            for line in lines:
                if "retour" in line.lower() or "16/02" in line:
                    continue
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

            message = (
                f"Heure de début : {start_str}\n"
                f"Heure de fin : {end_str}\n"
                f"Durée totale de la mission : {duration_str}\n"
            )

            if hours >= 16:
                message += "La personne a travaillé exceptionnellement longtemps aujourd’hui. Merci pour son implication."
            else:
                message += "La personne a accompli sa mission avec implication."

            # Création du texte à insérer
            packet = io.BytesIO()
            can = canvas.Canvas(packet, pagesize=A4)
            can.setFont("Helvetica-Bold", 11)
            y = 100
            for line in message.split("\n"):
                can.drawString(50, y, line)
                y += 15
            can.save()
            packet.seek(0)

            # Fusion PDF
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
                response.headers.set("Content-Type", "application/pdf")
                response.headers.set("Content-Disposition", "attachment", filename="pdf_modifie.pdf")
                response.headers.set("X-Duree", duration_str)  # Ajout d’un header perso avec la durée
            return response

        except Exception as e:
            return f"Erreur pendant le traitement : {str(e)}", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)