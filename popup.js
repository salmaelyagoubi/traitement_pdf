document.getElementById('analyzeBtn').addEventListener('click', () => {
    const fileInput = document.getElementById('pdfFile');
    const file = fileInput.files[0];
    if (!file) {
      alert("Choisis un fichier PDF");
      return;
    }
  
    const reader = new FileReader();
    reader.onload = async function () {
      const typedArray = new Uint8Array(reader.result);
      const pdf = await pdfjsLib.getDocument({ data: typedArray }).promise;
    
      let fullText = '';
      for (let i = 1; i <= pdf.numPages; i++) {
        const page = await pdf.getPage(i);
        const content = await page.getTextContent();
        const strings = content.items.map(item => item.str);
        fullText += strings.join(' ') + '\n';
      }
    
      // RegEx pour trouver les heures (ex : 08:00, 20h30, etc.)
      const timeRegex = /\b(\d{1,2})[:h](\d{2})\b/g;
      const matches = [...fullText.matchAll(timeRegex)];
    
      if (matches.length < 2) {
        document.getElementById('hours').innerText = "Pas assez d'heures détectées.";
        return;
      }
    
      // Extraire la première et dernière heure
      const first = matches[0];
      const last = matches[matches.length - 1];
    
      const startHour = parseInt(first[1]);
      const startMinute = parseInt(first[2]);
      const endHour = parseInt(last[1]);
      const endMinute = parseInt(last[2]);
    
      const start = new Date(0, 0, 0, startHour, startMinute);
      const end = new Date(0, 0, 0, endHour, endMinute);
    
      let diff = (end - start) / (1000 * 60 * 60);
      if (diff < 0) diff += 24; // si passage minuit
    
      const summary = diff >= 16
        ? `⏱ Durée : ${diff.toFixed(1)}h — La personne a travaillé plus de 16 heures ! 👏`
        : `⏱ Durée : ${diff.toFixed(1)}h — Journée normale.`
    
      document.getElementById('hours').innerText = summary;
    };
    reader.readAsArrayBuffer(file);
  });
  