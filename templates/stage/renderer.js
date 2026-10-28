const bg = document.getElementById("bg");
const floor = document.getElementById("floor");
const characterLayers = [
  document.getElementById("character-a"),
  document.getElementById("character-b"),
];
const card = document.getElementById("card");
const subtitle = document.getElementById("subtitle");
const progress = document.getElementById("progress");
const watermark = document.getElementById("watermark");

const POSITIONS = { left: 210, center: 660, right: 1120 };
const TRANSITION_MS = 180;

let payload = null;
let shots = [];
let progressItems = [];
let currentShot = -1;
let currentCharacter = "";
let activeLayer = 0;
let transition = null;

function easeOutCubic(x) {
  return 1 - Math.pow(1 - x, 3);
}

function preload(urls) {
  return Promise.all(
    urls.map(
      (url) =>
        new Promise((resolve, reject) => {
          const image = new Image();
          image.onload = () => resolve();
          image.onerror = () => reject(new Error(`failed to load ${url}`));
          image.src = url;
        })
    )
  );
}

function hideLayer(layer) {
  layer.style.display = "none";
  layer.style.opacity = "0";
}

function hideCharacters() {
  characterLayers.forEach(hideLayer);
  currentCharacter = "";
  transition = null;
}

function applyCharacterStyle(layer, character, offsetX = 0, breath = 0) {
  const stageWidth = payload?.width ?? 1920;
  const left =
    character.anchor_x != null
      ? character.anchor_x * stageWidth
      : POSITIONS[character.position] ?? POSITIONS.left;
  const bottom = character.anchor_y != null ? character.anchor_y : 52;
  const scale = character.scale ?? 1;
  const anchorShift = character.anchor_x != null ? " translateX(-50%)" : "";
  layer.style.left = `${left}px`;
  layer.style.bottom = `${bottom}px`;
  layer.style.height = `${character.height_px * scale}px`;
  layer.style.transform = `translateX(${offsetX.toFixed(2)}px)${anchorShift} translateY(${breath.toFixed(2)}px)`;
}

function startCharacterTransition(character, startMs) {
  if (currentCharacter === character.src) return;

  if (!currentCharacter) {
    activeLayer = 0;
    const layer = characterLayers[0];
    layer.src = character.src;
    layer.style.display = "block";
    layer.style.opacity = "1";
    layer.style.zIndex = "3";
    applyCharacterStyle(layer, character);
    hideLayer(characterLayers[1]);
    currentCharacter = character.src;
    transition = null;
    return;
  }

  const from = activeLayer;
  const to = activeLayer === 0 ? 1 : 0;
  const oldLayer = characterLayers[from];
  const newLayer = characterLayers[to];

  newLayer.src = character.src;
  newLayer.style.display = "block";
  newLayer.style.opacity = "0";
  newLayer.style.zIndex = "4";
  oldLayer.style.zIndex = "3";
  applyCharacterStyle(newLayer, character, 20, 0);
  currentCharacter = character.src;
  transition = { from, to, start: startMs, duration: TRANSITION_MS };
}

function updateCharacter(character, tMs, localMs) {
  const breath = character.motion === "idle_breathe" ? Math.sin(localMs / 700) * 3 : 0;

  if (transition) {
    const p = Math.min(1, Math.max(0, (tMs - transition.start) / transition.duration));
    const eased = easeOutCubic(p);
    const oldLayer = characterLayers[transition.from];
    const newLayer = characterLayers[transition.to];

    applyCharacterStyle(oldLayer, character, -30 * eased, breath);
    oldLayer.style.opacity = (1 - eased).toFixed(3);
    applyCharacterStyle(newLayer, character, 36 * (1 - eased), breath);
    newLayer.style.opacity = eased.toFixed(3);

    if (p >= 1) {
      activeLayer = transition.to;
      hideLayer(oldLayer);
      newLayer.style.zIndex = "3";
      newLayer.style.opacity = "1";
      applyCharacterStyle(newLayer, character, 0, breath);
      transition = null;
    }
    return;
  }

  const layer = characterLayers[activeLayer];
  layer.style.display = "block";
  layer.style.opacity = "1";
  layer.style.zIndex = "3";
  applyCharacterStyle(layer, character, 0, breath);
  hideLayer(characterLayers[activeLayer === 0 ? 1 : 0]);
}

window.initStage = async function (data) {
  payload = data;
  shots = data.shots;
  currentShot = -1;
  currentCharacter = "";
  transition = null;
  activeLayer = 0;
  characterLayers.forEach(hideLayer);

  watermark.textContent = data.watermark;
  bg.src = data.background;
  floor.src = data.floor;

  progress.innerHTML = "";
  progressItems = data.section_labels.map((label) => {
    const item = document.createElement("div");
    item.className = "progress-item";
    item.textContent = label;
    progress.appendChild(item);
    return item;
  });

  const urls = new Set([data.background, data.floor]);
  for (const shot of shots) {
    if (shot.character) urls.add(shot.character.src);
  }
  await preload([...urls]);
  await document.fonts.ready;

  window.renderAt(0);
  window.stageReady = true;
};

window.renderAt = function (tMs) {
  if (!payload || shots.length === 0) return;
  const last = shots[shots.length - 1];
  const t = Math.max(0, Math.min(tMs, last.end_ms));

  let index = shots.findIndex(
    (shot, i) => t >= shot.start_ms && (i === shots.length - 1 ? t <= shot.end_ms : t < shot.end_ms)
  );
  if (index < 0) index = shots.length - 1;
  const shot = shots[index];
  const local = t - shot.start_ms;

  if (shot.bg) bg.src = shot.bg;
  if (shot.floor) floor.src = shot.floor;

  if (index !== currentShot) {
    currentShot = index;
    if (shot.card_html) {
      card.innerHTML = shot.card_html;
      card.style.display = "block";
    } else {
      card.innerHTML = "";
      card.style.display = "none";
    }
  }

  if (shot.character) {
    if (currentCharacter !== shot.character.src) {
      startCharacterTransition(shot.character, shot.start_ms);
    }
    updateCharacter(shot.character, t, local);
  } else {
    hideCharacters();
  }

  const cardT = Math.min(1, Math.max(0, (local - 60) / 240));
  card.style.opacity = cardT.toFixed(3);
  card.style.transform = `translateY(${((1 - easeOutCubic(cardT)) * 18).toFixed(2)}px) scale(${(
    0.97 + 0.03 * easeOutCubic(cardT)
  ).toFixed(3)})`;

  const chunk = shot.subtitle_chunks.find((c) => t >= c.start_ms && t < c.end_ms);
  if (chunk) {
    const chunkT = Math.min(1, Math.max(0, (t - chunk.start_ms) / 70));
    subtitle.textContent = chunk.text;
    subtitle.style.opacity = chunkT.toFixed(3);
    subtitle.style.transform = `translateX(-50%) translateY(${((1 - chunkT) * 4).toFixed(1)}px)`;
  } else {
    subtitle.textContent = "";
    subtitle.style.opacity = "0";
  }

  progressItems.forEach((item, i) => {
    item.classList.toggle("active", i === shot.section_index);
  });
};
