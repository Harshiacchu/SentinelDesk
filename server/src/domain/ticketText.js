/** Same rule as contracts.ticket_text(): tolerate a null or empty subject. */
export function ticketText({ subject, body }) {
  const s = (subject ?? '').trim();
  const b = (body ?? '').trim();
  return s ? `${s}\n${b}` : b;
}
