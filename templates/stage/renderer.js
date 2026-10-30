const bg = document.getElementById("bg");
const floor = document.getElementById("floor");
const overlay = document.getElementById("overlay");
const characterLayers = [
  document.getElementById("character-a"),
  document.getElementById("character-b"),
];
const card = document.getElementById("card");
const subtitle = document.getElementById("subtitle");
const progress = document.getElementById("progress");
const watermark = document.getElementById("watermark");

const POSITIONS = { left: 210, center: 660, right: 1120 };
const OVERLAY_POSITIONS = { left: 25, center: 50, right: 75 };
const RUSH_MS = 280;
const RUSH_DISTANCE_RATIO = 0.65;
const OLD_FADE_DELAY_MS = 0;
const OLD_FADE_MS = 80;
const MOVE_MS = 240;

const imageCache = new Map();

let payload = null;
let shots = [];
let progressItems = [];
let currentShot = -1;
let currentCharacterSpec = null;
let activeLayer = 0;
let transition = null;

function easeOutCubic(x) {
  return 1 - Math.pow(1 - x, 3);
}

function easeOutQuad(x) {
  return 1 - (1 - x) * (1 - x);
}

function easeInCubic(x) {
  return x * x * x;
}

function preload(urls) {
  return Promise.all(
    urls.map(async (url) => {
      if (imageCache.has(url)) return imageCache.get(url);
      const image = new Image();
      await new Promise((resolve, reject) => {
        image.onload = () => resolve();
        image.onerror = () => reject(new Error(`failed to load ${url}`));
        image.src = url;
      });
      if (image.decode) {
        try {
          await image.decode();
        } catch (error) {
          // The browser may reject decode for an image it can still paint.
        }
      }
      imageCache.set(url, image);
      return image;
    })
  );
}

async function waitForPaint() {
  const images = [bg, floor, overlay, ...characterLayers].filter(Boolean);
  await Promise.all(
    images.map(async (image) => {
      if (image.style.display === "none") return;
      if (!image.complete) {
        await new Promise((resolve) => {
          image.addEventListener("load", resolve, { once: true });
          image.addEventListener("error", resolve, { once: true });
        });
      }
      if (image.decode) {
        try {
          await image.decode();
        } catch (error) {
          // Keep the already-cached frame instead of failing the shot.
        }
      }
    })
  );
  await new Promise((resolve) =>
    requestAnimationFrame(() => requestAnimationFrame(resolve))
  );
}

function hideLayer(layer) {
  layer.style.display = "none";
  layer.style.opacity = "0";
  layer.style.filter = "";
}

function hideCharacters() {
  characterLayers.forEach(hideLayer);
  currentCharacterSpec = null;
  transition = null;
  activeLayer = 0;
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

function characterMoveX(character, localMs) {
  const move = character.move;
  if (!move || move === "none") return 0;
  const progress = easeOutCubic(Math.min(1, Math.max(0, localMs / MOVE_MS)));
  if (move === "slide_in_left") return -18 * (1 - progress);
  if (move === "slide_in_right") return 18 * (1 - progress);
  if (move === "shift_left") return -10 * progress;
  if (move === "shift_right") return 10 * progress;
  return 0;
}

function rushDirection(character, seq) {
  if (!character) return "left";
  if (character.move === "slide_in_right" || character.move === "shift_right") {
    return "right";
  }
  if (character.move === "slide_in_left" || character.move === "shift_left") {
    return "left";
  }
  if (character.position === "right") return "right";
  if (character.position === "left") return "left";
  return seq % 2 === 0 ? "left" : "right";
}

function entryOffset(direction, eased) {
  const distance = (payload?.width ?? 1920) * RUSH_DISTANCE_RATIO;
  const start = direction === "right" ? distance : -distance;
  return start * (1 - eased);
}

function exitOffset(direction, progress) {
  const distance = payload?.width ?? 1920;
  const end = direction === "right" ? distance : -distance;
  return end * progress;
}

function showCharacterDirect(spec) {
  currentCharacterSpec = spec;
  transition = null;
  const layer = characterLayers[activeLayer];
  layer.src = spec.src;
  layer.style.display = "block";
  layer.style.opacity = "1";
  layer.style.zIndex = "3";
  layer.style.filter = "";
  applyCharacterStyle(layer, spec);
  hideLayer(characterLayers[activeLayer === 0 ? 1 : 0]);
}

function startCharacterTransition(fromSpec, toSpec, startMs, seq) {
  if (fromSpec && toSpec && fromSpec.src === toSpec.src) {
    showCharacterDirect(toSpec);
    return;
  }

  if (!fromSpec && !toSpec) {
    hideCharacters();
    return;
  }

  const fromLayerIndex = fromSpec ? activeLayer : -1;
  const toLayerIndex = fromSpec ? (activeLayer === 0 ? 1 : 0) : activeLayer;
  const direction = rushDirection(toSpec || fromSpec, seq);

  if (fromSpec) {
    const layer = characterLayers[fromLayerIndex];
    layer.src = fromSpec.src;
    layer.style.display = "block";
    layer.style.opacity = "1";
    layer.style.zIndex = "3";
    layer.style.filter = "";
    applyCharacterStyle(layer, fromSpec, 0, 0);
  }

  if (toSpec) {
    const layer = characterLayers[toLayerIndex];
    layer.src = toSpec.src;
    layer.style.display = "block";
    layer.style.opacity = "1";
    layer.style.zIndex = "4";
    applyCharacterStyle(layer, toSpec, entryOffset(direction, 0), 0);
  }

  currentCharacterSpec = toSpec;
  transition = {
    fromLayerIndex,
    toLayerIndex,
    fromSpec,
    toSpec,
    direction,
    start: startMs,
    duration: RUSH_MS,
  };
}

function syncCharacterForShot(shot) {
  const toSpec = shot.character;
  if (toSpec && currentCharacterSpec && currentCharacterSpec.src === toSpec.src) {
    showCharacterDirect(toSpec);
    return;
  }
  if (toSpec && !currentCharacterSpec && !shot.character_from && currentShot === 0) {
    showCharacterDirect(toSpec);
    return;
  }
  const fromSpec = shot.character_from || currentCharacterSpec || null;
  startCharacterTransition(fromSpec, toSpec, shot.start_ms, shot.seq);
}

function updateCharacter(character, tMs, localMs) {
  const breath = Math.sin(tMs / 700) * 3;

  if (transition) {
    const elapsed = Math.max(0, tMs - transition.start);
    const p = Math.min(1, elapsed / transition.duration);
    const eased = easeOutQuad(p);

    if (transition.fromSpec) {
      const oldLayer = characterLayers[transition.fromLayerIndex];
      if (transition.toSpec) {
        const fade = Math.min(
          1,
          Math.max(0, (elapsed - OLD_FADE_DELAY_MS) / OLD_FADE_MS)
        );
        oldLayer.style.opacity = (1 - fade).toFixed(3);
        oldLayer.style.filter = fade > 0
          ? `drop-shadow(0 10px 10px rgba(43, 43, 43, 0.22)) blur(${(fade * 2).toFixed(2)}px)`
          : "";
        applyCharacterStyle(oldLayer, transition.fromSpec, 0, breath);
      } else {
        oldLayer.style.opacity = "1";
        applyCharacterStyle(
          oldLayer,
          transition.fromSpec,
          exitOffset(transition.direction, easeInCubic(p)),
          breath
        );
      }
    }

    if (transition.toSpec) {
      const newLayer = characterLayers[transition.toLayerIndex];
      const blur = (1 - eased) * 1.2;
      newLayer.style.opacity = "1";
      newLayer.style.filter =
        `drop-shadow(0 10px 10px rgba(43, 43, 43, 0.22)) blur(${blur.toFixed(2)}px)`;
      applyCharacterStyle(
        newLayer,
        transition.toSpec,
        entryOffset(transition.direction, eased),
        breath
      );
    }

    if (p >= 1) {
      if (transition.fromSpec) {
        hideLayer(characterLayers[transition.fromLayerIndex]);
      }
      if (transition.toSpec) {
        activeLayer = transition.toLayerIndex;
        const newLayer = characterLayers[activeLayer];
        newLayer.style.zIndex = "3";
        newLayer.style.opacity = "1";
        newLayer.style.filter = "";
        applyCharacterStyle(
          newLayer,
          transition.toSpec,
          characterMoveX(transition.toSpec, localMs),
          breath
        );
      } else {
        characterLayers.forEach(hideLayer);
        activeLayer = 0;
      }
      transition = null;
    }
    return;
  }

  if (!currentCharacterSpec) {
    hideCharacters();
    return;
  }

  const layer = characterLayers[activeLayer];
  layer.src = currentCharacterSpec.src;
  layer.style.display = "block";
  layer.style.opacity = "1";
  layer.style.zIndex = "3";
  layer.style.filter = "";
  applyCharacterStyle(
    layer,
    currentCharacterSpec,
    characterMoveX(currentCharacterSpec, localMs),
    breath
  );
  hideLayer(characterLayers[activeLayer === 0 ? 1 : 0]);
}

window.initStage = async function (data, atMs = 0, preloadAll = true) {
  payload = data;
  shots = data.shots;
  currentShot = -1;
  currentCharacterSpec = null;
  transition = null;
  activeLayer = 0;
  characterLayers.forEach(hideLayer);
  window.stageReady = false;

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

  let urls;
  if (preloadAll) {
    urls = new Set([data.background, data.floor]);
    for (const shot of shots) {
      if (shot.bg) urls.add(shot.bg);
      if (shot.floor) urls.add(shot.floor);
      if (shot.overlay) urls.add(shot.overlay.src);
      if (shot.character) urls.add(shot.character.src);
      if (shot.character_from) urls.add(shot.character_from.src);
    }
  } else {
    const target =
      shots.find(
        (shot, i) =>
          atMs >= shot.start_ms &&
          (i === shots.length - 1 ? atMs <= shot.end_ms : atMs < shot.end_ms)
      ) ?? shots[0];
    urls = new Set([data.background, data.floor]);
    if (target.bg) urls.add(target.bg);
    if (target.floor) urls.add(target.floor);
    if (target.overlay) urls.add(target.overlay.src);
    if (target.character) urls.add(target.character.src);
    if (target.character_from) urls.add(target.character_from.src);
  }

  await preload([...urls]);
  await document.fonts.ready;

  window.renderAt(atMs);
  await waitForPaint();
  window.stageReady = true;
};

window.renderAt = function (tMs) {
  if (!payload || shots.length === 0) return;
  const last = shots[shots.length - 1];
  const t = Math.max(0, Math.min(tMs, last.end_ms));

  let index = shots.findIndex(
    (shot, i) =>
      t >= shot.start_ms &&
      (i === shots.length - 1 ? t <= shot.end_ms : t < shot.end_ms)
  );
  if (index < 0) index = shots.length - 1;
  const shot = shots[index];
  const local = t - shot.start_ms;

  if (index !== currentShot) {
    currentShot = index;
    syncCharacterForShot(shot);
    card.classList.toggle("card-left", shot.card_side === "left");
    if (shot.card_html) {
      card.innerHTML = shot.card_html;
      card.style.display = "block";
    } else {
      card.innerHTML = "";
      card.style.display = "none";
    }
    card.style.opacity = "1";
    card.style.transform = "none";
  }

  if (shot.bg && bg.getAttribute("src") !== shot.bg) bg.src = shot.bg;
  if (shot.floor && floor.getAttribute("src") !== shot.floor) floor.src = shot.floor;
  if (shot.overlay) {
    if (overlay.getAttribute("src") !== shot.overlay.src) {
      overlay.src = shot.overlay.src;
    }
    overlay.style.display = "block";
    overlay.style.left = `${OVERLAY_POSITIONS[shot.overlay.position] ?? 50}%`;
    overlay.style.width = `${shot.overlay.width_px}px`;
    overlay.style.bottom = `${shot.overlay.bottom}px`;
    overlay.style.opacity = String(shot.overlay.opacity);
    overlay.style.mixBlendMode = shot.overlay.blend;
  } else {
    overlay.style.display = "none";
    overlay.removeAttribute("src");
  }

  updateCharacter(shot.character, t, local);

  const chunk = shot.subtitle_chunks.find(
    (c) => t >= c.start_ms && t < c.end_ms
  );
  if (chunk) {
    subtitle.textContent = chunk.text;
    subtitle.style.opacity = "1";
    subtitle.style.transform = "translateX(-50%)";
  } else {
    subtitle.textContent = "";
    subtitle.style.opacity = "0";
  }

  progressItems.forEach((item, i) => {
    item.classList.toggle("active", i === shot.section_index);
  });
};
