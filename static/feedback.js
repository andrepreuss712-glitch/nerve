(function(){
  function openModal(){document.getElementById('nerve-fb-modal').classList.add('show');}
  function closeModal(){document.getElementById('nerve-fb-modal').classList.remove('show');}

  async function submit(ev){
    ev.preventDefault();
    var form = ev.target;
    var fd = new FormData(form);
    fd.set('context_url', location.pathname + location.search);
    try{
      var res = await fetch('/api/feedback', {method:'POST', body:fd, credentials:'same-origin'});
      if(!res.ok){
        var j = await res.json().catch(function(){return{};});
        alert('Feedback fehlgeschlagen: ' + (j.error || res.status));
        return;
      }
      form.reset();
      closeModal();
      var t = document.createElement('div');
      t.style.cssText = 'position:fixed;bottom:24px;right:24px;background:#00D4AA;color:#0D1117;padding:12px 18px;border-radius:10px;font-weight:600;z-index:10000;font-family:inherit';
      t.textContent = 'Danke fuer dein Feedback!';
      document.body.appendChild(t);
      setTimeout(function(){t.remove();}, 3000);
    }catch(e){
      alert('Netzwerkfehler');
    }
  }

  function init(){
    var btn = document.getElementById('nerve-fb-btn');
    if(btn){btn.addEventListener('click', openModal);}
    var modal = document.getElementById('nerve-fb-modal');
    if(modal){
      modal.addEventListener('click', function(e){if(e.target === modal) closeModal();});
      var cancel = modal.querySelector('.nerve-fb-cancel');
      if(cancel) cancel.addEventListener('click', closeModal);
      var form = modal.querySelector('form');
      if(form) form.addEventListener('submit', submit);
    }
  }

  if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
