// Keep one camera controller per mounted component across Streamlit reruns.
export default function ({parentElement, data, setTriggerValue}) {
  const video = parentElement.querySelector("video");
  if (!video.guide) video.guide = createGuide(parentElement, video);
  video.guide.send = setTriggerValue;
  video.guide.receive(data);
  return () => {
    if (!video.isConnected) video.guide.dispose();
  };
}

function createGuide(root, video) {
  const start = root.querySelector("#start");
  const voice = root.querySelector("#voice");
  const status = root.querySelector("#status");
  const canvas = document.createElement("canvas");
  const synth = window.speechSynthesis;
  let enabled = Boolean(synth);
  let running = false;
  let generation = 0;
  let timer, pending, sentAt, previous, lastSpoken;
  let lastSpokenAt = -Infinity;

  function show(text) {
    if (status.textContent !== text) status.textContent = text;
  }
  function speak(text) {
    if (!enabled) return;
    synth.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "en";
    synth.speak(utterance);
  }
  function stop(message) {
    generation++;
    running = false;
    clearInterval(timer);
    pending = previous = lastSpoken = null;
    lastSpokenAt = -Infinity;
    video.srcObject?.getTracks().forEach(track => track.stop());
    video.srcObject = null;
    video.hidden = true;
    start.textContent = "Start camera";
    synth?.cancel();
    show(message);
  }
  function fail(message) {
    stop(message);
    speak(message);
  }
  function capture() {
    if (pending) {
      if (performance.now() - sentAt > 8000) fail("Detection timed out. Start the camera to reconnect.");
      return;
    }
    if (video.readyState < 2 || !video.videoWidth) return;
    const scale = Math.min(1, 640 / Math.max(video.videoWidth, video.videoHeight));
    canvas.width = Math.round(video.videoWidth * scale);
    canvas.height = Math.round(video.videoHeight * scale);
    canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
    pending = crypto.randomUUID();
    sentAt = performance.now();
    guide.send("frame", {id: pending, jpeg: canvas.toDataURL("image/jpeg", .78).split(",")[1]});
  }
  start.onclick = async () => {
    if (running) return stop("Camera off.");
    if (!navigator.mediaDevices?.getUserMedia) return fail("Camera access requires HTTPS or localhost.");
    running = true;
    const session = ++generation;
    start.textContent = "Stop camera";
    show("Waiting for camera permission.");
    speak("Starting camera.");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {facingMode: {ideal: "environment"}}, audio: false
      });
      if (session !== generation) {
        stream.getTracks().forEach(track => track.stop());
        return;
      }
      video.srcObject = stream;
      stream.getVideoTracks()[0].onended = () => {
        if (session === generation) fail("Camera disconnected.");
      };
      video.hidden = false;
      await video.play();
      if (session !== generation) return;
      show("Looking for objects.");
      timer = setInterval(capture, 500);
      capture();
    } catch (error) {
      if (session === generation) fail("Camera unavailable. Check camera permission and try again.");
    }
  };
  voice.disabled = !synth;
  if (!synth) voice.textContent = "Speech unavailable in this browser";
  function updateVoice() {
    voice.setAttribute("aria-pressed", String(enabled));
    status.setAttribute("aria-live", enabled ? "off" : "polite");
    if (synth) voice.textContent = enabled ? "Spoken descriptions on" : "Spoken descriptions off";
  }
  updateVoice();
  voice.onclick = () => {
    enabled = !enabled;
    updateVoice();
    if (enabled) speak(status.textContent);
    else synth.cancel();
  };
  const dispose = () => stop("Camera off.");
  window.addEventListener("pagehide", dispose);
  const guide = {
    receive(reply) {
      if (!running || !reply || reply.id !== pending) return;
      pending = null;
      if (reply.error) return fail(reply.error);
      const now = performance.now();
      if (now - sentAt > 2500) {
        show("Detection delayed.");
        previous = null;
        return;
      }
      show(reply.text);
      // Wait for confirmation on consecutive frames and avoid repeating a stable scene.
      if (reply.text === previous && reply.text !== lastSpoken && now - lastSpokenAt > 2200) {
        speak(reply.text);
        lastSpoken = reply.text;
        lastSpokenAt = now;
      }
      previous = reply.text;
    },
    dispose() {
      window.removeEventListener("pagehide", dispose);
      dispose();
    }
  };
  return guide;
}
