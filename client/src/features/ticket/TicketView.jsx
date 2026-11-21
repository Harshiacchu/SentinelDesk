import { useEffect, useMemo, useState } from 'react';
import { TicketHeader } from './TicketHeader.jsx';
import { OutagePulse } from './OutagePulse.jsx';
import { ReplyPanel } from './ReplyPanel.jsx';
import { ActionCard } from './ActionCard.jsx';
import { FeedbackCard } from './FeedbackCard.jsx';
import { DetailCards } from './DetailCards.jsx';
import { DetailDrawer } from './DetailDrawer.jsx';
import { buildDetails } from './detailModel.js';
import { PiiNotice } from './PiiNotice.jsx';
import { ChangeBanner } from './ChangeBanner.jsx';
import { HistoryCard } from './HistoryCard.jsx';
import { TopPrecedents } from './TopPrecedents.jsx';

/** Composes the one-screen workspace. Owns only UI state; data changes go through callbacks. */
export function TicketView({ ticket, incident, busy, onAction, onFeedback, onAddNote, onTrackIncident, onFollowUp, onEditDraft, translation }) {
  const [openDetail, setOpenDetail] = useState(null);
  const [picked, setPicked] = useState(null);
  useEffect(() => { setPicked(null); }, [ticket.ticketId]);
  const details = useMemo(() => buildDetails(ticket), [ticket]);

  return (
    <>
      <TicketHeader ticket={ticket} />
      <ChangeBanner lastChange={ticket.lastChange} />
      <PiiNotice pii={ticket.pii} />
      <div className="ticket-grid">
        <div className="ticket-left">
          {incident && <OutagePulse incident={incident} onTrack={() => onTrackIncident(incident.key)} />}
          <ReplyPanel key={ticket.ticketId} ticket={ticket} busy={busy} onEditDraft={onEditDraft} translation={translation} picked={picked} onPick={setPicked} />
          <TopPrecedents ticket={ticket} picked={picked} />
          <HistoryCard key={`h-${ticket.ticketId}`} ticket={ticket} busy={busy} onFollowUp={onFollowUp} translation={translation} />
        </div>
        <aside className="ticket-right">
          <ActionCard key={ticket.ticketId} ticket={ticket} busy={busy} onAction={onAction} />
          <FeedbackCard ticket={ticket} busy={busy} onFeedback={onFeedback} />
        </aside>
      </div>
      <DetailCards details={details} onOpen={setOpenDetail} />
      <DetailDrawer ticket={ticket} details={details} openId={openDetail} onSelect={setOpenDetail} onClose={() => setOpenDetail(null)} onAddNote={onAddNote} />
    </>
  );
}
