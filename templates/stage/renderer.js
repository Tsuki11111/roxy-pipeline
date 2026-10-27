const bg = document.getElementById("bg");
const floor = document.getElementById("floor");
const character = document.getElementById("character");
const card = document.getElementById("card");
const subtitle = document.getElementById("subtitle");
const progress = document.getElementById("progress");
const watermark = document.getElementById("watermark");

const POSITIONS = { left: 210, center: 660, right: 1120 };

let payload = null;
let shots = [];
let progressItems = [];
let currentShot = -1;
let currentCharacter = "";

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

window.initStage = async function (data) {
  payload = data;
  shots = data.shots;
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
    if (shot.character) {
      if (currentCharacter !== shot.character.src) {
        character.src = shot.character.src;
        currentCharacter = shot.character.src;
      }
      character.style.display = "block";
      character.style.left = `${POSITIONS[shot.character.position] ?? POSITIONS.left}px`;
      character.style.height = `${shot.character.height_px}px`;
    } else {
      character.style.display = "none";
    }

    if (shot.card_html) {
      card.innerHTML = shot.card_html;
      card.style.display = "block";
    } else {
      card.innerHTML = "";
      card.style.display = "none";
    }
  }

  if (shot.character) {
    const breath =
      shot.character.motion === "idle_breathe" ? Math.sin(local / 700) * 3 : 0;
    character.style.transform = `translateY(${breath.toFixed(2)}px)`;
  }

  const cardT = Math.min(1, Math.max(0, (local - 80) / 320));
  card.style.opacity = cardT.toFixed(3);
  card.style.transform = `translateY(${((1 - easeOutCubic(cardT)) * 18).toFixed(2)}px) scale(${(
    0.97 + 0.03 * easeOutCubic(cardT)
  ).toFixed(3)})`;

  const chunk = shot.subtitle_chunks.find((c) => t >= c.start_ms && t < c.end_ms);
  subtitle.textContent = chunk ? chunk.text : "";
  subtitle.style.opacity = chunk ? "1" : "0";

  progressItems.forEach((item, i) => {
    item.classList.toggle("active", i === shot.section_index);
  });
};
