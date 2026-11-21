/** Placeholder knowledge base for the mock provider (shape mirrors real KB rows). */
export const PRECEDENTS = {
  VPN: [
    { ticketId: 'TKT-00042', subject: 'VPN down for all remote staff', snippet: 'Expired certificate on the VPN gateway; renewed it and restarted the service.', language: 'en', similarity: 0.86 },
    { ticketId: 'TKT-05518', subject: 'Remote access unavailable', snippet: 'Failed over to the backup concentrator; access restored in 20 minutes.', language: 'en', similarity: 0.79 },
    { ticketId: 'TKT-01377', subject: 'Keine VPN-Verbindung', snippet: 'VPN-Client neu gestartet und auf die neueste Version aktualisiert.', language: 'de', similarity: 0.77 },
  ],
  Login: [
    { ticketId: 'TKT-20811', subject: 'Password reset link expired', snippet: 'Reset links expire quickly; requested a new one from the self-service portal.', language: 'en', similarity: 0.91 },
    { ticketId: 'TKT-03390', subject: 'Reset email not arriving', snippet: 'Reset mail was filtered as spam; confirmed the address on file.', language: 'en', similarity: 0.88 },
    { ticketId: 'TKT-11902', subject: 'Kennwort abgelaufen', snippet: 'Passwort über das Portal zurückgesetzt und Konto entsperrt.', language: 'de', similarity: 0.84 },
  ],
  Email: [
    { ticketId: 'TKT-07731', subject: 'Outlook not syncing', snippet: 'Recreated the mail profile; mailbox synced again.', language: 'en', similarity: 0.83 },
    { ticketId: 'TKT-16620', subject: 'Postfach voll', snippet: 'Archivierung aktiviert und Postfachgröße erhöht.', language: 'de', similarity: 0.8 },
  ],
  Network: [
    { ticketId: 'TKT-04410', subject: 'Office network down', snippet: 'Core switch rebooted after a firmware fault; connectivity restored.', language: 'en', similarity: 0.82 },
    { ticketId: 'TKT-12087', subject: 'WLAN im Büro gestört', snippet: 'Access Point neu gestartet, Kanal gewechselt.', language: 'de', similarity: 0.78 },
  ],
  Printer: [
    { ticketId: 'TKT-08821', subject: 'Network printer offline', snippet: 'Removed the printer and re-added it by IP address; it came back online.', language: 'en', similarity: 0.87 },
    { ticketId: 'TKT-14460', subject: 'Drucker druckt nicht', snippet: 'Druckspooler-Dienst neu gestartet, Warteschlange geleert.', language: 'de', similarity: 0.85 },
  ],
  Billing: [
    { ticketId: 'TKT-11230', subject: 'Credit request after outage', snippet: 'Acknowledged the outage and passed the credit request to billing for review.', language: 'en', similarity: 0.81 },
    { ticketId: 'TKT-09917', subject: 'Erstattung angefragt', snippet: 'Erstattungsanfrage an die Buchhaltung weitergeleitet, Prüfung läuft.', language: 'de', similarity: 0.77 },
  ],
  Database: [
    { ticketId: 'TKT-06602', subject: 'Database connection errors', snippet: 'Connection pool exhausted; raised the limit and restarted the app service.', language: 'en', similarity: 0.8 },
  ],
  Other: [
    { ticketId: 'TKT-19004', subject: 'General question', snippet: 'Forwarded to the product team for a detailed answer.', language: 'en', similarity: 0.58 },
  ],
};

/** Draft sentences per topic: [text, sourceIndex|null]. */
export const DRAFTS = {
  VPN: {
    en: [['We know the VPN is unavailable and our on-call team is working on it. ', 0], ['A similar outage was previously fixed by renewing the gateway certificate. ', 0], ['We will update you as soon as access is back.', null]],
    de: [['Wir wissen, dass das VPN nicht erreichbar ist, und unser Bereitschaftsteam arbeitet daran. ', 0], ['Ein ähnlicher Ausfall wurde zuletzt durch ein erneuertes Gateway-Zertifikat behoben. ', 0], ['Wir melden uns, sobald der Zugang wieder funktioniert.', null]],
  },
  Login: {
    en: [['Please request a new reset link from the self-service portal, as links expire quickly. ', 0], ['If the email does not arrive, check your spam folder. ', 1]],
    de: [['Bitte fordern Sie im Self-Service-Portal einen neuen Link an, da Links schnell ablaufen. ', 0], ['Falls keine E-Mail ankommt, prüfen Sie bitte Ihren Spam-Ordner.', 1]],
  },
  Email: {
    en: [['Please recreate your mail profile; this restored syncing in a similar case. ', 0]],
    de: [['Bitte legen Sie Ihr Mailprofil neu an; das hat in einem ähnlichen Fall geholfen. ', 0]],
  },
  Network: {
    en: [['We are checking the network equipment at your site. ', 0], ['We will update you once connectivity is confirmed.', null]],
    de: [['Wir prüfen die Netzwerktechnik an Ihrem Standort. ', 0], ['Wir melden uns, sobald die Verbindung bestätigt ist.', null]],
  },
  Printer: {
    en: [['Please remove the printer from the list and add it again using its IP address. ', 0], ['If it stays offline, restart the print spooler service.', 1]],
    de: [['Bitte entfernen Sie den Drucker aus der Liste und fügen Sie ihn über seine IP-Adresse neu hinzu. ', 0], ['Falls er offline bleibt, starten Sie bitte den Druckspooler-Dienst neu.', 1]],
  },
  Billing: {
    en: [['Thank you for contacting us about the service interruption. ', 0], ['Our billing team will review your account and reply.', 1]],
    de: [['Vielen Dank für Ihre Nachricht zur Unterbrechung. ', 0], ['Unsere Buchhaltung prüft Ihr Konto und meldet sich.', 1]],
  },
  Database: {
    en: [['We are looking into the database connection errors. ', 0], ['We will update you shortly.', null]],
    de: [['Wir untersuchen die Datenbankfehler. ', 0], ['Wir melden uns in Kürze.', null]],
  },
  Other: {
    en: [['Thank you for your message. A team member will follow up with details.', null]],
    de: [['Vielen Dank für Ihre Nachricht. Ein Teammitglied meldet sich mit Details.', null]],
  },
};

export const QUEUE_BY_TOPIC = {
  VPN: 'IT Support', Login: 'Customer Service', Email: 'IT Support', Network: 'Technical Support',
  Printer: 'IT Support', Billing: 'Billing and Payments', Database: 'Technical Support', Other: 'Product Support',
};
