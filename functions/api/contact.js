const MAX_FILES = 5;
const MAX_FILE_BYTES = 10 * 1024 * 1024;
const ALLOWED_MIME = new Set([
  'image/jpeg',
  'image/png',
  'image/webp',
  'image/gif',
  'image/heic',
  'image/heif',
]);

function jsonResponse(payload, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Cache-Control': 'no-store',
    },
  });
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function arrayBufferToBase64(buffer) {
  const bytes = new Uint8Array(buffer);
  const chunkSize = 0x8000;
  let binary = '';
  for (let i = 0; i < bytes.length; i += chunkSize) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunkSize));
  }
  return btoa(binary);
}

export async function onRequestPost(context) {
  const { request, env } = context;

  try {
    const formData = await request.formData();

    // Honeypot tegen spam
    const website = String(formData.get('website') || '').trim();
    if (website) {
      return jsonResponse({
        ok: true,
        melding: 'Bedankt voor uw aanvraag! We nemen zo spoedig mogelijk contact met u op.',
      });
    }

    const naam = String(formData.get('naam') || '').trim();
    const telefoon = String(formData.get('telefoon') || '').trim();
    const email = String(formData.get('email') || '').trim();
    const woonplaats = String(formData.get('woonplaats') || '').trim();
    const bericht = String(formData.get('bericht') || '').trim();

    if (!naam || !telefoon || !bericht) {
      return jsonResponse({
        ok: false,
        melding: 'Vul alstublieft uw naam, telefoonnummer en bericht in.',
      }, 400);
    }

    if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      return jsonResponse({
        ok: false,
        melding: 'Vul een geldig e-mailadres in of laat het veld leeg.',
      }, 400);
    }

    const rawFotos = formData.getAll('fotos').filter(
      (item) => item && typeof item === 'object' && typeof item.arrayBuffer === 'function' && item.size > 0
    );

    if (rawFotos.length > MAX_FILES) {
      return jsonResponse({
        ok: false,
        melding: 'U kunt maximaal 5 foto\'s tegelijk meesturen.',
      }, 400);
    }

    const attachments = [];
    for (const file of rawFotos) {
      if (file.size > MAX_FILE_BYTES) {
        return jsonResponse({
          ok: false,
          melding: `Het bestand "${file.name}" is groter dan 10 MB.`,
        }, 400);
      }
      if (file.type && !ALLOWED_MIME.has(file.type.toLowerCase())) {
        return jsonResponse({
          ok: false,
          melding: `Het bestand "${file.name}" heeft geen ondersteund afbeeldingsformaat.`,
        }, 400);
      }
      const buffer = await file.arrayBuffer();
      attachments.push({
        filename: file.name || 'tuinfoto.jpg',
        content: arrayBufferToBase64(buffer),
      });
    }

    if (!env.RESEND_API_KEY) {
      return jsonResponse({
        ok: false,
        melding: 'E-mailverzending is nog niet geconfigureerd op de server (RESEND_API_KEY ontbreekt). Bel ons gerust op +31 6 46057599.',
      }, 500);
    }

    const toAddress = env.MAIL_TO || 't.jansen283@proton.me';
    const fromAddress = env.MAIL_FROM || 'Van Ravenswaaij Tuinen <onboarding@resend.dev>';

    const tekstInhoud = [
      'Nieuwe offerte- / contactaanvraag via de website:',
      '',
      `Naam: ${naam}`,
      `Telefoon: ${telefoon}`,
      `E-mail: ${email || 'Niet opgegeven'}`,
      `Postcode / woonplaats: ${woonplaats || 'Niet opgegeven'}`,
      `Bijgevoegde foto's: ${attachments.length}`,
      '',
      'Bericht:',
      bericht,
    ].join('\n');

    const htmlInhoud = `
      <h2>Nieuwe aanvraag via Van Ravenswaaij Tuinen</h2>
      <p><strong>Naam:</strong> ${escapeHtml(naam)}</p>
      <p><strong>Telefoon:</strong> <a href="tel:${escapeHtml(telefoon)}">${escapeHtml(telefoon)}</a></p>
      <p><strong>E-mail:</strong> ${email ? `<a href="mailto:${escapeHtml(email)}">${escapeHtml(email)}</a>` : 'Niet opgegeven'}</p>
      <p><strong>Postcode / woonplaats:</strong> ${escapeHtml(woonplaats || 'Niet opgegeven')}</p>
      <p><strong>Bijgevoegde foto's:</strong> ${attachments.length}</p>
      <p><strong>Bericht:</strong><br>${escapeHtml(bericht).replace(/\n/g, '<br>')}</p>
    `;

    const mailPayload = {
      from: fromAddress,
      to: [toAddress],
      subject: `Nieuwe tuinaanvraag van ${naam}${woonplaats ? ` (${woonplaats})` : ''}`,
      text: tekstInhoud,
      html: htmlInhoud,
    };

    if (email) {
      mailPayload.reply_to = email;
    }
    if (attachments.length > 0) {
      mailPayload.attachments = attachments;
    }

    const resendRes = await fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${env.RESEND_API_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(mailPayload),
    });

    if (!resendRes.ok) {
      return jsonResponse({
        ok: false,
        melding: 'Het versturen van de e-mail is mislukt. Probeer het later opnieuw of bel +31 6 46057599.',
      }, 502);
    }

    return jsonResponse({
      ok: true,
      melding: 'Bedankt voor uw aanvraag! We nemen zo spoedig mogelijk contact met u op.',
    });
  } catch (err) {
    return jsonResponse({
      ok: false,
      melding: 'Er is een fout opgetreden bij het verwerken van uw aanvraag. Bel ons gerust op +31 6 46057599.',
    }, 500);
  }
}