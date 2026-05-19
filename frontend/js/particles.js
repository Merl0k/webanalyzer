(function(){
  const canvas = document.getElementById('particles-canvas');
  if(!canvas) return;
  const ctx = canvas.getContext('2d');
  let W, H, particles=[], animId;
  const COUNT = 55;

  function getColor() {
    return getComputedStyle(document.documentElement).getPropertyValue('--particle-color').trim()||'255,255,255';
  }
  function getTheme() { return document.documentElement.getAttribute('data-theme')||'dark'; }

  function resize(){ W = canvas.width = window.innerWidth; H = canvas.height = window.innerHeight; }

  function makeParticle(){
    return { x:Math.random()*W, y:Math.random()*H, vx:(Math.random()-.5)*.4, vy:(Math.random()-.5)*.4, r:Math.random()*2+.5, o:Math.random()*.5+.1 };
  }

  function init(){
    resize(); particles=[];
    for(let i=0;i<COUNT;i++) particles.push(makeParticle());
    if(animId) cancelAnimationFrame(animId);
    loop();
  }

  function loop(){
    ctx.clearRect(0,0,W,H);
    const col = getColor(), theme = getTheme();
    particles.forEach(p=>{
      p.x+=p.vx; p.y+=p.vy;
      if(p.x<0)p.x=W; if(p.x>W)p.x=0;
      if(p.y<0)p.y=H; if(p.y>H)p.y=0;
      particles.forEach(q=>{
        const dx=p.x-q.x,dy=p.y-q.y,dist=Math.sqrt(dx*dx+dy*dy);
        if(dist<100){ctx.beginPath();ctx.strokeStyle=`rgba(${col},${(1-dist/100)*0.12})`;ctx.lineWidth=.5;ctx.moveTo(p.x,p.y);ctx.lineTo(q.x,q.y);ctx.stroke();}
      });
      if(theme==='cyberpunk'){ctx.fillStyle=`rgba(${col},${p.o})`;ctx.fillRect(p.x,p.y,p.r*1.5,p.r*1.5);}
      else if(theme==='light'){ctx.beginPath();ctx.arc(p.x,p.y,p.r*2,0,Math.PI*2);ctx.strokeStyle=`rgba(${col},${p.o*.6})`;ctx.lineWidth=1;ctx.stroke();}
      else{ctx.beginPath();ctx.arc(p.x,p.y,p.r,0,Math.PI*2);ctx.fillStyle=`rgba(${col},${p.o})`;ctx.fill();}
    });
    animId = requestAnimationFrame(loop);
  }

  window.addEventListener('resize', resize);
  new MutationObserver(()=>init()).observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});
  init();
})();
