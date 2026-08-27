const t=(e,a="item")=>String(e||"").toLowerCase().replace(/[^a-z0-9\u4e00-\u9fa5]/g,"-").replace(/-+/g,"-").replace(/^-|-$/g,"").slice(0,32)||a;export{t as g};
