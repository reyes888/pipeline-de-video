function connectProjectWS(projectId, onMessage) {
  let ws = null;
  let closedByUser = false;
  let retryDelay = 500;
  let reconnectTimer = null;

  function detach(socket) {
    if (!socket) return;
    socket.onopen = null;
    socket.onmessage = null;
    socket.onclose = null;
    socket.onerror = null;
    try { socket.close(); } catch (e) { /* ignore */ }
  }

  function open() {
    if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
    detach(ws); // nunca dejar el socket anterior vivo escuchando en paralelo

    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${proto}://${location.host}/ws/${projectId}`);
    ws.onopen = () => { retryDelay = 500; };
    ws.onmessage = (evt) => {
      try { onMessage(JSON.parse(evt.data)); } catch (e) { /* ignore */ }
    };
    ws.onclose = () => {
      if (closedByUser) return;
      reconnectTimer = setTimeout(open, retryDelay);
      retryDelay = Math.min(retryDelay * 1.6, 8000);
    };
    ws.onerror = () => { ws.close(); };
  }

  open();

  return {
    close() {
      closedByUser = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      detach(ws);
    },
  };
}
