const tokenKey='homework_magic_message_token';
const emailKey='homework_magic_message_email';
const form=document.getElementById('message-form');
const statusBox=document.getElementById('form-status');
const list=document.getElementById('messages');
const emailInput=document.getElementById('email');
emailInput.value=localStorage.getItem(emailKey)||'';

function addText(parent,tag,text,className=''){const el=document.createElement(tag);el.textContent=text;if(className)el.className=className;parent.appendChild(el);return el;}
function render(items){list.replaceChildren();if(!items.length){addText(list,'p','No messages yet.','muted');return;}for(const item of items){const box=document.createElement('article');box.className='message-item';addText(box,'h3',item.subject);addText(box,'p',`${item.status} · ${new Date(item.created_at).toLocaleString()}`,'muted');addText(box,'p',item.message,'original');for(const reply of item.replies||[]){const r=document.createElement('div');r.className='reply';addText(r,'strong',reply.admin_name);addText(r,'p',reply.reply);addText(r,'small',new Date(reply.created_at).toLocaleString());box.appendChild(r);}list.appendChild(box);}}
async function loadMessages(){const token=localStorage.getItem(tokenKey)||'';const email=emailInput.value.trim()||localStorage.getItem(emailKey)||'';const qs=new URLSearchParams();if(token)qs.set('access_token',token);if(email)qs.set('email',email);const res=await fetch(`/api/messages?${qs}`);if(res.ok){const data=await res.json();render(data.messages||[]);}}
form.addEventListener('submit',async e=>{e.preventDefault();statusBox.textContent='Sending…';const payload={email:emailInput.value.trim()||null,category:document.getElementById('category').value,subject:document.getElementById('subject').value.trim(),message:document.getElementById('message').value.trim()};const res=await fetch('/api/messages',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const data=await res.json();if(!res.ok){statusBox.textContent=data.detail||'Could not send message.';return;}localStorage.setItem(tokenKey,data.message.access_token);localStorage.setItem(emailKey,data.message.user_email);statusBox.textContent='Message sent.';form.reset();emailInput.value=localStorage.getItem(emailKey)||'';await loadMessages();});
document.getElementById('refresh').addEventListener('click',loadMessages);loadMessages();
