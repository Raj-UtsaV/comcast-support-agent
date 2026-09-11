const $ = id => document.getElementById(id);
let conversation = null;
let sending = false;
const chat = $('chat-form'), staff = $('staff-form');
function paragraph(parent, text, tag = 'p') {
  const node = document.createElement(tag); node.textContent = text; parent.append(node); return node;
}
function showResult(result) {
  const root = $('result'); root.replaceChildren();
  paragraph(root, `Request category: ${result.intent || 'Unknown'}`, 'h3');
  paragraph(root, `Model confidence (uncalibrated): ${result.intent_confidence.toFixed(2)}`);
  paragraph(root, result.decision === 'escalate' ? 'Escalate to human support' : 'Auto-handle candidate — no message has been sent');
  paragraph(root, result.decision_reason);
  paragraph(root, 'Suggested reply', 'h3'); paragraph(root, result.draft_reply);
  const download = paragraph(root, 'Download reply', 'button'); download.type = 'button';
  download.onclick = () => { const url = URL.createObjectURL(new Blob([result.draft_reply], {type: 'text/plain'})); const link = document.createElement('a'); link.href = url; link.download = 'support-reply.txt'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); };
  if (result.reply_status === 'safe_fallback') paragraph(root, 'A configured fallback replaced an unavailable or unverified draft.');
  if (result.safety_flags.length) paragraph(root, `Safety signals: ${result.safety_flags.join(', ')}`);
  const details = document.createElement('details'); root.append(details);
  paragraph(details, 'Historical evidence — resolution unverified', 'summary');
  for (const match of result.retrieved_examples) {
    paragraph(details, `${match.evidence.evidence_id} · Similarity: ${match.similarity.toFixed(3)}`, 'h4');
    paragraph(details, `Customer: ${match.evidence.customer_text}`);
    paragraph(details, `Historical reply: ${match.evidence.reply_text}`);
  }
}
async function submit(event) {
  event.preventDefault(); const form = event.currentTarget;
  if (sending || !form.reportValidity() || !$('message').value.trim()) return;
  sending = true;
  const message = $('message').value; $('error').textContent = '';
  const buttons = document.querySelectorAll('button'); buttons.forEach(b => b.disabled = true);
  if (staff) ['company', 'example', 'history'].forEach(id => $(id).disabled = true);
  $('message').disabled = true;
  let pending = null;
  if (staff) $('result').textContent = 'Analysing the request…';
  else {
    paragraph($('messages'), `You: ${message}`, 'article').className = 'customer-message';
    $('message').value = '';
    pending = paragraph($('messages'), 'Support: Thinking…', 'article');
    pending.className = 'support-message pending-message';
    pending.setAttribute('role', 'status');
    pending.scrollIntoView({block: 'nearest', behavior: 'smooth'});
  }
  try {
    const payload = staff ? {message, company: $('company').value, history: JSON.parse($('history').value)} : {message, conversation};
    const response = await fetch(staff ? '/api/analyse' : '/api/chat', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
    const data = await response.json(); if (!response.ok) throw new Error(data.error || 'The request failed. Please try again.');
    if (staff) showResult(data.result);
    else {
      pending.textContent = `Support: ${data.reply}`;
      pending.classList.remove('pending-message');
      pending.removeAttribute('role');
      pending.scrollIntoView({block: 'nearest', behavior: 'smooth'});
      while ($('messages').children.length > 100) $('messages').firstChild.remove();
      conversation = data.conversation; $('message').value = '';
    }
  } catch (error) {
    $('error').textContent = error.message;
    if (staff) $('result').textContent = 'No reply available.';
    else {
      pending.textContent = 'Reply unavailable. Your message was not added to the conversation. Edit or send it again below.';
      pending.className = 'support-message failed-message';
      pending.removeAttribute('role');
      $('message').value = message;
    }
  }
  finally { sending = false; if (staff) ['company', 'example', 'history'].forEach(id => $(id).disabled = false); buttons.forEach(b => b.disabled = false); $('message').disabled = false; $('message').focus(); }
}
(chat || staff)?.addEventListener('submit', submit);
$('reset')?.addEventListener('click', () => { conversation = null; $('messages').replaceChildren(); $('error').textContent = ''; $('message').value = ''; });
document.querySelectorAll('[data-prompt]').forEach(button => button.onclick = () => { $('message').value = button.dataset.prompt; chat.requestSubmit(); });
$('example')?.addEventListener('change', event => { $('message').value = event.target.value; $('result').textContent = 'Select Analyse to review this message.'; });
if (staff) ['message', 'history'].forEach(id => $(id).addEventListener('input', () => $('result').textContent = 'Select Analyse to review this message.'));

if (chat) $('message').addEventListener('keydown', event => {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing && event.keyCode !== 229) {
    event.preventDefault();
    if (!event.repeat && !$('message').disabled && $('message').value.trim()) chat.requestSubmit();
  }
});
