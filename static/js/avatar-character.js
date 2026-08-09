'use strict';

(function initialiseHomeworkMagicAvatar(global) {
  if (global.HomeworkMagicAvatar) return;

  // Character pages keep loading this one shared JavaScript entry point. The
  // character stylesheet is requested only when a figure is actually drawn,
  // so changing its appearance never requires cache-version edits in HTML.
  const AVATAR_STYLESHEET_PATH = '/static/css/avatar-character.css';
  let avatarStylesheetPromise = null;

  function ensureStylesheet() {
    if (avatarStylesheetPromise) return avatarStylesheetPromise;
    const doc = global.document;
    if (!doc || !doc.createElement) {
      avatarStylesheetPromise = Promise.resolve(null);
      return avatarStylesheetPromise;
    }

    let stylesheet = doc.getElementById('homework-magic-avatar-styles');
    if (!stylesheet) {
      stylesheet = doc.createElement('link');
      stylesheet.id = 'homework-magic-avatar-styles';
      stylesheet.rel = 'stylesheet';
      stylesheet.href = AVATAR_STYLESHEET_PATH;
      stylesheet.setAttribute('data-homework-magic-avatar-styles', '');
      (doc.head || doc.documentElement).appendChild(stylesheet);
    }

    if (stylesheet.sheet) {
      avatarStylesheetPromise = Promise.resolve(stylesheet);
      return avatarStylesheetPromise;
    }

    avatarStylesheetPromise = new Promise((resolve) => {
      stylesheet.addEventListener('load', () => resolve(stylesheet), {once: true});
      stylesheet.addEventListener('error', () => {
        console.warn('The learner character styles could not be loaded.');
        resolve(null);
      }, {once: true});
    });
    return avatarStylesheetPromise;
  }

  const PROFILE_DEFAULTS = Object.freeze({
    character: 'girl',
    clothes: 'pink_dress',
    bottoms: 'match_outfit',
    shoes: 'trainers',
    skin_tone: 'warm',
    hair_colour: 'brown',
    hair_length: 'long',
    hair_style: 'ponytail',
    eye_shape: 'round',
    eye_colour: 'green',
    nose: 'button',
    mouth: 'smile',
    eyebrows: 'arched',
  });

  const CHARACTER_PRESETS = Object.freeze({
    girl: {
      clothes: 'pink_dress',
      bottoms: 'pink_dress',
      shoes: 'trainers',
      hair_colour: 'brown',
      hair_length: 'long',
      hair_style: 'ponytail',
      eye_shape: 'round',
      eye_colour: 'green',
      nose: 'button',
      mouth: 'smile',
      eyebrows: 'arched',
    },
    boy: {
      clothes: 'blue_tshirt',
      bottoms: 'navy_trousers',
      shoes: 'boots',
      hair_colour: 'black',
      hair_length: 'short',
      hair_style: 'spiky',
      eye_shape: 'almond',
      eye_colour: 'brown',
      nose: 'small',
      mouth: 'smile',
      eyebrows: 'straight',
    },
  });

  const OPTIONS = Object.freeze({
    character: [
      {value: 'girl', label: 'Girl character', symbol: '👧'},
      {value: 'boy', label: 'Boy character', symbol: '👦'},
    ],
    clothes: [
      {value: 'purple_hoodie', label: 'Purple hoodie', symbol: '💜'},
      {value: 'blue_tshirt', label: 'Blue T-shirt', symbol: '👕'},
      {value: 'green_jumper', label: 'Green jumper', symbol: '🌿'},
      {value: 'pink_dress', label: 'Pink dress', symbol: '🌸'},
      {value: 'star_jacket', label: 'Star jacket', symbol: '⭐'},
      {value: 'sunshine_dungarees', label: 'Sunshine dungarees', symbol: '☀️'},
    ],
    bottoms: [
      {value: 'match_outfit', label: 'Match my outfit', symbol: '✨'},
      {value: 'navy_trousers', label: 'Navy trousers', symbol: '👖'},
      {value: 'blue_jeans', label: 'Blue jeans', symbol: '🩵'},
      {value: 'purple_trousers', label: 'Purple trousers', symbol: '💜'},
      {value: 'pink_dress', label: 'Pink dress', symbol: '👗'},
      {value: 'purple_dress', label: 'Purple dress', symbol: '👗'},
    ],
    shoes: [
      {value: 'trainers', label: 'Colourful trainers', symbol: '👟'},
      {value: 'boots', label: 'Adventure boots', symbol: '🥾'},
      {value: 'school_shoes', label: 'Smart school shoes', symbol: '👞'},
      {value: 'rainbow_high_tops', label: 'Rainbow high-tops', symbol: '🌈'},
    ],
    skin_tone: [
      {value: 'light', label: 'Light skin tone', symbol: '●', swatch: '#f2c9aa'},
      {value: 'warm', label: 'Warm skin tone', symbol: '●', swatch: '#d99a70'},
      {value: 'tan', label: 'Tan skin tone', symbol: '●', swatch: '#ae704d'},
      {value: 'deep', label: 'Deep skin tone', symbol: '●', swatch: '#70462f'},
    ],
    hair_colour: [
      {value: 'black', label: 'Black hair', symbol: '●', swatch: '#28242a'},
      {value: 'brown', label: 'Brown hair', symbol: '●', swatch: '#6f442d'},
      {value: 'blonde', label: 'Blonde hair', symbol: '●', swatch: '#e3bd62'},
      {value: 'red', label: 'Red hair', symbol: '●', swatch: '#ad4e32'},
      {value: 'purple', label: 'Purple hair', symbol: '●', swatch: '#8b6bd6'},
      {value: 'teal', label: 'Teal hair', symbol: '●', swatch: '#278f8a'},
    ],
    hair_length: [
      {value: 'short', label: 'Short'},
      {value: 'medium', label: 'Medium'},
      {value: 'long', label: 'Long'},
    ],
    hair_style: [
      {value: 'straight', label: 'Straight'},
      {value: 'ponytail', label: 'Ponytail'},
      {value: 'spiky', label: 'Spiky'},
    ],
    eye_shape: [
      {value: 'round', label: 'Round'},
      {value: 'almond', label: 'Almond'},
      {value: 'smiling', label: 'Smiling'},
    ],
    eye_colour: [
      {value: 'brown', label: 'Brown eyes', symbol: '●', swatch: '#6a432e'},
      {value: 'blue', label: 'Blue eyes', symbol: '●', swatch: '#3f85bc'},
      {value: 'green', label: 'Green eyes', symbol: '●', swatch: '#4d8a62'},
      {value: 'grey', label: 'Grey eyes', symbol: '●', swatch: '#7d8490'},
    ],
    nose: [
      {value: 'button', label: 'Button'},
      {value: 'small', label: 'Small'},
      {value: 'round', label: 'Round'},
    ],
    mouth: [
      {value: 'smile', label: 'Happy smile'},
      {value: 'grin', label: 'Toothy grin'},
      {value: 'open', label: 'Excited smile'},
      {value: 'calm', label: 'Calm smile'},
    ],
    eyebrows: [
      {value: 'soft', label: 'Soft eyebrows'},
      {value: 'straight', label: 'Straight eyebrows'},
      {value: 'arched', label: 'Arched eyebrows'},
    ],
  });

  const ATTRIBUTES = Object.freeze({
    character: 'data-character',
    clothes: 'data-clothes',
    bottoms: 'data-bottoms',
    shoes: 'data-shoes',
    skin_tone: 'data-skin-tone',
    hair_colour: 'data-hair-colour',
    hair_length: 'data-hair-length',
    hair_style: 'data-hair-style',
    eye_shape: 'data-eye-shape',
    eye_colour: 'data-eye-colour',
    nose: 'data-nose',
    mouth: 'data-mouth',
    eyebrows: 'data-eyebrows',
  });

  const XP_STAGES = Object.freeze([
    {stage: 1, threshold: 0, name: 'Little Learner'},
    {stage: 2, threshold: 100, name: 'Curious Explorer'},
    {stage: 3, threshold: 500, name: 'Growing Star'},
    {stage: 4, threshold: 1000, name: 'Clever Champion'},
    {stage: 5, threshold: 2000, name: 'Super Scholar'},
    {stage: 6, threshold: 5000, name: 'Learning Legend'},
  ]);

  const AGE_SCALES = Object.freeze({5: 0.84, 6: 0.88, 7: 0.92, 8: 0.96,
    9: 1, 10: 1.04, 11: 1.08});
  const XP_SCALES = Object.freeze({1: 0.95, 2: 0.97, 3: 0.99,
    4: 1, 5: 1.02, 6: 1.04});
  const GIRL_PROPORTION_TRANSFORMS = Object.freeze({
    head: 'matrix(0.86 0 0 0.86 12.6 13.44)',
    torso: 'matrix(0.8 0 0 1 18 0)',
    lower: 'matrix(0.88 0 0 1 10.8 0)',
    armLeft: 'translate(6 0)',
    armRight: 'translate(-6 0)',
  });
  const SKIN_PALETTES = Object.freeze({
    light: ['#ffe5d1', '#f2c9aa', '#cf9674'],
    warm: ['#f4c19c', '#d99a70', '#aa6748'],
    tan: ['#d69a72', '#ae704d', '#75432f'],
    deep: ['#9e6b4d', '#70462f', '#3e2419'],
  });
  const HAIR_PALETTES = Object.freeze({
    black: ['#5d5668', '#29262e', '#111014'],
    brown: ['#aa734e', '#6f442d', '#352017'],
    blonde: ['#ffe7a0', '#e3bd62', '#9d7326'],
    red: ['#e98258', '#ad4e32', '#642718'],
    purple: ['#b9a1ef', '#8061c7', '#422d7b'],
    teal: ['#72ccc5', '#278f8a', '#14504e'],
  });
  const EYE_PALETTES = Object.freeze({
    brown: ['#c58b5c', '#75472e', '#382015'],
    blue: ['#98d8ff', '#3f85bc', '#18466d'],
    green: ['#a4dfad', '#4d8a62', '#254d33'],
    grey: ['#d0d6df', '#7d8490', '#404651'],
  });
  const OUTFIT_PALETTES = Object.freeze({
    purple_hoodie: ['#b7a5ff', '#765ed1', '#44318f'],
    blue_tshirt: ['#83c9f5', '#347fc4', '#1b4f84'],
    green_jumper: ['#78d4b7', '#239477', '#11604d'],
    pink_dress: ['#ffb8d2', '#f24f94', '#b72164'],
    star_jacket: ['#7291e7', '#3656a9', '#20316b'],
    sunshine_dungarees: ['#ffe278', '#f0aa2b', '#b56b13'],
  });
  const TROUSER_PALETTES = Object.freeze({
    purple_hoodie: ['#7b90b5', '#49567e', '#293955'],
    blue_tshirt: ['#6986ad', '#344c72', '#1e2c44'],
    green_jumper: ['#6f9892', '#365f5a', '#1e3e3a'],
    pink_dress: ['#9d84ac', '#685478', '#3d2f49'],
    star_jacket: ['#737b9f', '#3c4365', '#22263e'],
    sunshine_dungarees: ['#7db0d4', '#3f78a7', '#244a69'],
  });
  const BOTTOM_PALETTES = Object.freeze({
    navy_trousers: ['#6682ad', '#324a72', '#1d2c48'],
    blue_jeans: ['#82b6dc', '#477fae', '#28516f'],
    purple_trousers: ['#b39ce2', '#7558b5', '#44306f'],
    pink_dress: ['#ffb8d2', '#f24f94', '#b72164'],
    purple_dress: ['#d6b6ff', '#8b5cf6', '#5631a5'],
  });
  const SHOE_PALETTES = Object.freeze({
    trainers: ['#ffb15f', '#ef6f78', '#8e3c55'],
    boots: ['#c99469', '#95613f', '#53341f'],
    school_shoes: ['#697180', '#303644', '#151922'],
    rainbow_high_tops: ['#ff5f7d', '#ffd85d', '#4b75dc'],
  });
  const SVG_NS = 'http://www.w3.org/2000/svg';
  let figureSequence = 0;
  const actionTimers = new WeakMap();

  function optionValue(group, value) {
    const options = OPTIONS[group] || [];
    return options.some((option) => option.value === value)
      ? value : PROFILE_DEFAULTS[group];
  }

  function profileCopy(profile) {
    const source = profile && typeof profile === 'object' ? profile : {};
    const safe = {};
    Object.keys(PROFILE_DEFAULTS).forEach((group) => {
      safe[group] = optionValue(group, String(source[group] || ''));
    });
    safe.customised = Boolean(source.customised);
    return safe;
  }

  function ageDetails(value, yearGroup) {
    let age = Number(value);
    const year = Number(yearGroup);
    if (!Number.isFinite(age) && Number.isFinite(year)) age = year + 5;
    if (!Number.isFinite(age)) age = 7;
    age = Math.max(5, Math.min(11, Math.round(age)));
    let stage = 1;
    let label = 'Little Adventurer';
    if (age >= 11) {
      stage = 4;
      label = 'Future Leader';
    } else if (age >= 9) {
      stage = 3;
      label = 'Bold Builder';
    } else if (age >= 7) {
      stage = 2;
      label = 'Bright Explorer';
    }
    return {age, stage, label, scale: AGE_SCALES[age] || 1};
  }

  function growthForXp(value) {
    const xp = Math.max(0, Number(value) || 0);
    let current = XP_STAGES[0];
    let next = XP_STAGES[1] || null;
    XP_STAGES.forEach((stage, index) => {
      if (xp >= stage.threshold) {
        current = stage;
        next = XP_STAGES[index + 1] || null;
      }
    });
    const progress = next
      ? Math.round((xp - current.threshold)
          / Math.max(1, next.threshold - current.threshold) * 100)
      : 100;
    return {
      stage: current.stage,
      name: current.name,
      lifetime_xp: xp,
      progress_percent: Math.max(0, Math.min(100, progress)),
      xp_to_next: next ? Math.max(0, next.threshold - xp) : 0,
      next_stage: next ? {
        stage: next.stage,
        name: next.name,
        threshold: next.threshold,
      } : null,
    };
  }

  function normaliseState(summary, learner) {
    const source = summary && typeof summary === 'object' ? summary : {};
    const student = learner && typeof learner === 'object' ? learner : {};
    return {
      profile: profileCopy(source.profile),
      growth: growthForXp(source.growth && source.growth.lifetime_xp),
      age: ageDetails(student.age, student.year_group),
    };
  }

  function svgElement(tagName, attributes, className) {
    const node = document.createElementNS(SVG_NS, tagName);
    if (className) node.setAttribute('class', className);
    Object.keys(attributes || {}).forEach((name) => {
      node.setAttribute(name, String(attributes[name]));
    });
    return node;
  }

  function addSvg(parent, tagName, attributes, className) {
    const node = svgElement(tagName, attributes, className);
    parent.appendChild(node);
    return node;
  }

  function addStop(gradient, offset, className) {
    addSvg(gradient, 'stop', {offset}, className);
  }

  function addLinearGradient(defs, id, classes) {
    const gradient = addSvg(defs, 'linearGradient', {
      id, x1: '20%', y1: '0%', x2: '80%', y2: '100%'
    });
    addStop(gradient, '0%', classes[0]);
    addStop(gradient, '52%', classes[1]);
    addStop(gradient, '100%', classes[2]);
  }

  function addRadialGradient(defs, id, classes) {
    const gradient = addSvg(defs, 'radialGradient', {
      id, cx: '34%', cy: '26%', r: '76%'
    });
    addStop(gradient, '0%', classes[0]);
    addStop(gradient, '64%', classes[1]);
    addStop(gradient, '100%', classes[2]);
  }

  function addRainbowGradient(defs, id) {
    const gradient = addSvg(defs, 'linearGradient', {
      id, x1: '0%', y1: '10%', x2: '100%', y2: '90%'
    });
    [
      ['0%', '#ff5f7d'],
      ['18%', '#ff9154'],
      ['36%', '#ffd85d'],
      ['54%', '#64d49b'],
      ['72%', '#4bc4e8'],
      ['87%', '#5f78e8'],
      ['100%', '#a765dc'],
    ].forEach((stop) => {
      addSvg(gradient, 'stop', {offset: stop[0], 'stop-color': stop[1]});
    });
  }

  function buildDefinitions(svg, prefix) {
    const defs = addSvg(svg, 'defs');
    addRadialGradient(defs, `${prefix}-skin`, [
      'hm-avatar3d-stop-skin-light',
      'hm-avatar3d-stop-skin',
      'hm-avatar3d-stop-skin-shadow',
    ]);
    addLinearGradient(defs, `${prefix}-hair`, [
      'hm-avatar3d-stop-hair-light',
      'hm-avatar3d-stop-hair',
      'hm-avatar3d-stop-hair-shadow',
    ]);
    addLinearGradient(defs, `${prefix}-outfit`, [
      'hm-avatar3d-stop-outfit-light',
      'hm-avatar3d-stop-outfit',
      'hm-avatar3d-stop-outfit-shadow',
    ]);
    addLinearGradient(defs, `${prefix}-trousers`, [
      'hm-avatar3d-stop-trousers-light',
      'hm-avatar3d-stop-trousers',
      'hm-avatar3d-stop-trousers-shadow',
    ]);
    addLinearGradient(defs, `${prefix}-shoe`, [
      'hm-avatar3d-stop-shoe-light',
      'hm-avatar3d-stop-shoe',
      'hm-avatar3d-stop-shoe-shadow',
    ]);
    addRainbowGradient(defs, `${prefix}-rainbow-shoe`);
    addRadialGradient(defs, `${prefix}-eye`, [
      'hm-avatar3d-stop-eye-light',
      'hm-avatar3d-stop-eye',
      'hm-avatar3d-stop-eye-shadow',
    ]);
    const shadow = addSvg(defs, 'filter', {
      id: `${prefix}-shadow`, x: '-35%', y: '-30%', width: '170%', height: '180%'
    });
    addSvg(shadow, 'feDropShadow', {
      dx: '0', dy: '4', stdDeviation: '3', 'flood-color': '#29304a',
      'flood-opacity': '.23'
    });
  }

  function buildHair(rig, fills) {
    const proportions = addSvg(rig, 'g', {},
      'hm-avatar3d-proportions hm-avatar3d-proportions-head');
    const back = addSvg(proportions, 'g', {}, 'hm-avatar3d-hair-back-group');
    addSvg(back, 'path', {
      d: 'M45 108 C36 75 45 39 89 33 C133 38 145 73 136 111 L130 168 C116 153 64 153 50 168 Z',
      fill: fills.hair,
    }, 'hm-avatar3d-hair-back hm-avatar3d-hair-long');
    addSvg(back, 'path', {
      d: 'M46 104 C38 71 52 39 90 35 C128 39 142 71 134 106 C121 116 60 116 46 104 Z',
      fill: fills.hair,
    }, 'hm-avatar3d-hair-back hm-avatar3d-hair-short');
    const ponytail = addSvg(back, 'g', {}, 'hm-avatar3d-ponytail');
    addSvg(ponytail, 'path', {
      d: 'M130 67 C161 70 164 109 145 144 C137 158 125 147 131 131 C142 103 145 85 126 78 Z',
      fill: fills.hair,
    }, 'hm-avatar3d-hair-piece');
    addSvg(ponytail, 'ellipse', {cx: '132', cy: '77', rx: '8', ry: '7'},
      'hm-avatar3d-hair-band');
  }

  function buildLegsAndShoes(rig, fills) {
    const proportions = addSvg(rig, 'g', {},
      'hm-avatar3d-proportions hm-avatar3d-proportions-lower');
    const lower = addSvg(proportions, 'g', {}, 'hm-avatar3d-lower-body');
    const leftLeg = addSvg(lower, 'g', {}, 'hm-avatar3d-leg hm-avatar3d-leg-left');
    addSvg(leftLeg, 'rect', {x: '57', y: '174', width: '25', height: '56', rx: '12', fill: fills.trousers},
      'hm-avatar3d-trouser');
    addSvg(leftLeg, 'rect', {x: '60', y: '205', width: '20', height: '28', rx: '10', fill: fills.skin},
      'hm-avatar3d-dress-leg');
    const rightLeg = addSvg(lower, 'g', {}, 'hm-avatar3d-leg hm-avatar3d-leg-right');
    addSvg(rightLeg, 'rect', {x: '98', y: '174', width: '25', height: '56', rx: '12', fill: fills.trousers},
      'hm-avatar3d-trouser');
    addSvg(rightLeg, 'rect', {x: '100', y: '205', width: '20', height: '28', rx: '10', fill: fills.skin},
      'hm-avatar3d-dress-leg');

    const shoes = addSvg(lower, 'g', {}, 'hm-avatar3d-shoes');
    const left = addSvg(shoes, 'g', {}, 'hm-avatar3d-shoe hm-avatar3d-shoe-left');
    addSvg(left, 'path', {
      d: 'M49 222 Q57 214 79 218 Q91 222 90 235 Q89 242 78 243 L51 241 Q43 237 49 222 Z',
      fill: fills.shoe,
    }, 'hm-avatar3d-shoe-base');
    addSvg(left, 'path', {
      d: 'M49 222 Q57 214 79 218 Q91 222 90 235 Q89 242 78 243 L51 241 Q43 237 49 222 Z',
      fill: fills.rainbowShoe,
    }, 'hm-avatar3d-rainbow-shoe-base');
    const right = addSvg(shoes, 'g', {}, 'hm-avatar3d-shoe hm-avatar3d-shoe-right');
    addSvg(right, 'path', {
      d: 'M91 235 Q90 222 101 218 Q123 214 131 222 Q137 237 129 241 L102 243 Q92 242 91 235 Z',
      fill: fills.shoe,
    }, 'hm-avatar3d-shoe-base');
    addSvg(right, 'path', {
      d: 'M91 235 Q90 222 101 218 Q123 214 131 222 Q137 237 129 241 L102 243 Q92 242 91 235 Z',
      fill: fills.rainbowShoe,
    }, 'hm-avatar3d-rainbow-shoe-base');
    addSvg(left, 'path', {d: 'M54 231 Q68 226 84 231'}, 'hm-avatar3d-shoe-lace');
    addSvg(left, 'path', {d: 'M54 235 Q69 232 86 235'}, 'hm-avatar3d-shoe-sole');
    addSvg(left, 'path', {d: 'M58 228 L64 234 L70 227 L76 233'}, 'hm-avatar3d-rainbow-stripe');
    addSvg(right, 'path', {d: 'M96 231 Q111 226 126 231'}, 'hm-avatar3d-shoe-lace');
    addSvg(right, 'path', {d: 'M94 235 Q111 232 126 235'}, 'hm-avatar3d-shoe-sole');
    addSvg(right, 'path', {d: 'M102 228 L108 234 L114 227 L120 233'}, 'hm-avatar3d-rainbow-stripe');
  }

  function buildBody(rig, fills) {
    const proportions = addSvg(rig, 'g', {},
      'hm-avatar3d-proportions hm-avatar3d-proportions-torso');
    addSvg(proportions, 'rect', {x: '80', y: '119', width: '20', height: '25', rx: '9', fill: fills.skin},
      'hm-avatar3d-neck');
    const body = addSvg(proportions, 'g', {}, 'hm-avatar3d-body-group');
    addSvg(body, 'path', {
      d: 'M58 127 Q90 116 122 127 Q137 142 135 181 Q115 191 90 191 Q65 191 45 181 Q43 142 58 127 Z',
      fill: fills.outfit,
    }, 'hm-avatar3d-torso');
    addSvg(body, 'path', {
      d: 'M54 163 Q90 153 126 163 L141 207 Q91 221 39 207 Z',
      fill: fills.trousers,
    }, 'hm-avatar3d-dress-skirt');

    const hoodie = addSvg(body, 'g', {}, 'hm-avatar3d-clothes-detail hm-avatar3d-hoodie-detail');
    addSvg(hoodie, 'path', {d: 'M64 127 Q90 146 116 127 Q110 114 90 113 Q70 114 64 127 Z'},
      'hm-avatar3d-hood');
    addSvg(hoodie, 'path', {d: 'M85 130 L84 151 M95 130 L96 151'}, 'hm-avatar3d-clothes-line');
    addSvg(hoodie, 'path', {d: 'M68 163 Q90 154 112 163 L108 178 Q90 183 72 178 Z'},
      'hm-avatar3d-pocket');

    const tshirt = addSvg(body, 'g', {}, 'hm-avatar3d-clothes-detail hm-avatar3d-tshirt-detail');
    addSvg(tshirt, 'path', {d: 'M77 127 Q90 138 103 127'}, 'hm-avatar3d-collar-line');
    addSvg(tshirt, 'path', {d: 'M90 145 L94 153 L103 154 L96 160 L98 169 L90 165 L82 169 L84 160 L77 154 L86 153 Z'},
      'hm-avatar3d-shirt-star');

    const jumper = addSvg(body, 'g', {}, 'hm-avatar3d-clothes-detail hm-avatar3d-jumper-detail');
    addSvg(jumper, 'path', {d: 'M76 128 Q90 143 104 128'}, 'hm-avatar3d-collar-line');
    addSvg(jumper, 'path', {d: 'M56 151 H124 M53 161 H127 M51 171 H129'},
      'hm-avatar3d-knit-lines');

    const dress = addSvg(body, 'g', {}, 'hm-avatar3d-clothes-detail hm-avatar3d-dress-detail');
    addSvg(dress, 'path', {d: 'M68 129 Q90 148 112 129'}, 'hm-avatar3d-collar-line');
    addSvg(dress, 'path', {d: 'M51 178 Q90 190 129 178'}, 'hm-avatar3d-dress-belt');
    addSvg(dress, 'circle', {cx: '67', cy: '199', r: '3'}, 'hm-avatar3d-dress-dot');
    addSvg(dress, 'circle', {cx: '90', cy: '204', r: '3'}, 'hm-avatar3d-dress-dot');
    addSvg(dress, 'circle', {cx: '113', cy: '199', r: '3'}, 'hm-avatar3d-dress-dot');

    const jacket = addSvg(body, 'g', {}, 'hm-avatar3d-clothes-detail hm-avatar3d-jacket-detail');
    addSvg(jacket, 'path', {d: 'M90 125 V184'}, 'hm-avatar3d-jacket-zip');
    addSvg(jacket, 'path', {d: 'M64 142 L67 149 L75 150 L69 155 L71 163 L64 159 L57 163 L59 155 L53 150 L61 149 Z'},
      'hm-avatar3d-jacket-star');
    addSvg(jacket, 'path', {d: 'M97 163 Q110 158 123 163'}, 'hm-avatar3d-jacket-pocket');

    const dungarees = addSvg(body, 'g', {}, 'hm-avatar3d-clothes-detail hm-avatar3d-dungarees-detail');
    addSvg(dungarees, 'path', {d: 'M67 127 L74 153 H106 L113 127 M73 152 V183 H107 V152'},
      'hm-avatar3d-dungaree-lines');
    addSvg(dungarees, 'circle', {cx: '76', cy: '151', r: '3'}, 'hm-avatar3d-dungaree-button');
    addSvg(dungarees, 'circle', {cx: '104', cy: '151', r: '3'}, 'hm-avatar3d-dungaree-button');
    addSvg(dungarees, 'path', {d: 'M82 163 Q90 169 98 163'}, 'hm-avatar3d-dungaree-pocket');
  }

  function buildArms(rig, fills) {
    const leftProportions = addSvg(rig, 'g', {},
      'hm-avatar3d-proportions hm-avatar3d-proportions-arm-left');
    const left = addSvg(leftProportions, 'g', {}, 'hm-avatar3d-arm hm-avatar3d-arm-left');
    addSvg(left, 'path', {
      d: 'M59 136 Q43 137 34 157 L25 181 Q23 193 34 196 Q45 197 49 184 L61 154 Z',
      fill: fills.outfit,
    }, 'hm-avatar3d-sleeve hm-avatar3d-sleeve-long');
    addSvg(left, 'path', {
      d: 'M59 136 Q47 137 39 151 L47 166 Q52 162 58 164 L61 154 Z',
      fill: fills.outfit,
    }, 'hm-avatar3d-sleeve hm-avatar3d-sleeve-short');
    addSvg(left, 'path', {
      d: 'M47 162 Q41 166 37 175 L26 184 Q23 194 34 197 Q45 197 49 185 L57 165 Q52 161 47 162 Z',
      fill: fills.skin,
    }, 'hm-avatar3d-tshirt-forearm');
    addSvg(left, 'path', {d: 'M43 158 Q51 161 58 164'}, 'hm-avatar3d-tshirt-cuff');
    addSvg(left, 'circle', {cx: '31', cy: '191', r: '11', fill: fills.skin}, 'hm-avatar3d-hand');
    const rightProportions = addSvg(rig, 'g', {},
      'hm-avatar3d-proportions hm-avatar3d-proportions-arm-right');
    const right = addSvg(rightProportions, 'g', {}, 'hm-avatar3d-arm hm-avatar3d-arm-right');
    addSvg(right, 'path', {
      d: 'M121 136 Q137 137 146 157 L155 181 Q157 193 146 196 Q135 197 131 184 L119 154 Z',
      fill: fills.outfit,
    }, 'hm-avatar3d-sleeve hm-avatar3d-sleeve-long');
    addSvg(right, 'path', {
      d: 'M121 136 Q133 137 141 151 L133 166 Q128 162 122 164 L119 154 Z',
      fill: fills.outfit,
    }, 'hm-avatar3d-sleeve hm-avatar3d-sleeve-short');
    addSvg(right, 'path', {
      d: 'M133 162 Q139 166 143 175 L154 184 Q157 194 146 197 Q135 197 131 185 L123 165 Q128 161 133 162 Z',
      fill: fills.skin,
    }, 'hm-avatar3d-tshirt-forearm');
    addSvg(right, 'path', {d: 'M137 158 Q129 161 122 164'}, 'hm-avatar3d-tshirt-cuff');
    addSvg(right, 'circle', {cx: '149', cy: '191', r: '11', fill: fills.skin}, 'hm-avatar3d-hand');
    addSvg(right, 'path', {d: 'M144 191 Q149 185 154 191 M146 196 Q150 190 155 195'},
      'hm-avatar3d-fingers');
  }

  function buildEye(head, x, side, fills) {
    const eye = addSvg(head, 'g', {}, `hm-avatar3d-eye hm-avatar3d-eye-${side}`);
    addSvg(eye, 'ellipse', {cx: String(x), cy: '91', rx: '13', ry: '10'},
      'hm-avatar3d-eye-white');
    addSvg(eye, 'circle', {cx: String(x), cy: '92', r: '7', fill: fills.eye},
      'hm-avatar3d-iris');
    addSvg(eye, 'circle', {cx: String(x), cy: '93', r: '3.5'}, 'hm-avatar3d-pupil');
    addSvg(eye, 'circle', {cx: String(x - 2), cy: '89', r: '2.2'}, 'hm-avatar3d-eye-glint');
    addSvg(eye, 'circle', {cx: String(x + 2), cy: '94', r: '1'}, 'hm-avatar3d-eye-glint-small');
    addSvg(eye, 'path', {
      d: `M${x - 9} 90.5 Q${x} 83.8 ${x + 9} 90.5`,
    }, 'hm-avatar3d-girl-eyelid');
    const lashes = side === 'left'
      ? `M${x - 8.5} 88 L${x - 13} 84.8 M${x - 9.5} 90.5 L${x - 14.5} 88.5`
      : `M${x + 8.5} 88 L${x + 13} 84.8 M${x + 9.5} 90.5 L${x + 14.5} 88.5`;
    addSvg(eye, 'path', {d: lashes}, 'hm-avatar3d-girl-eyelashes');
  }

  function buildFace(rig, fills) {
    const proportions = addSvg(rig, 'g', {},
      'hm-avatar3d-proportions hm-avatar3d-proportions-head');
    const head = addSvg(proportions, 'g', {}, 'hm-avatar3d-head-group');
    addSvg(head, 'circle', {cx: '45', cy: '89', r: '14', fill: fills.skin}, 'hm-avatar3d-ear');
    addSvg(head, 'circle', {cx: '135', cy: '89', r: '14', fill: fills.skin}, 'hm-avatar3d-ear');
    addSvg(head, 'path', {
      d: 'M90 41 C122 41 138 63 136 96 C134 126 116 144 90 148 C64 144 46 126 44 96 C42 63 58 41 90 41 Z',
      fill: fills.skin,
    }, 'hm-avatar3d-face hm-avatar3d-face-girl');
    addSvg(head, 'path', {
      d: 'M90 42 C122 42 139 63 136 96 C133 126 116 143 90 147 C64 143 47 126 44 96 C41 63 58 42 90 42 Z',
      fill: fills.skin,
    }, 'hm-avatar3d-face hm-avatar3d-face-boy');
    addSvg(head, 'path', {
      d: 'M113 48 C133 62 138 91 128 119 C122 135 108 143 92 147 C116 140 127 122 129 97 C131 75 125 59 113 48 Z'
    }, 'hm-avatar3d-face-shadow');
    addSvg(head, 'ellipse', {cx: '72', cy: '64', rx: '20', ry: '11'}, 'hm-avatar3d-face-highlight');

    const hair = addSvg(head, 'g', {}, 'hm-avatar3d-hair-front-group');
    addSvg(hair, 'path', {
      d: 'M44 81 C42 49 60 30 91 31 C119 31 136 50 136 78 C122 68 116 53 111 49 C102 66 82 72 62 62 C57 72 51 79 44 81 Z',
      fill: fills.hair,
    }, 'hm-avatar3d-hair-front hm-avatar3d-hair-straight');
    addSvg(hair, 'path', {
      d: 'M40 85 C39 64 47 49 61 43 C77 36 103 36 119 43 C133 49 141 64 140 85 C123 73 58 73 40 85 Z',
      fill: fills.hair,
    }, 'hm-avatar3d-hair-front hm-avatar3d-hair-spiky hm-avatar3d-hair-spiky-cap');
    addSvg(hair, 'path', {
      d: 'M40 83 L43 56 L54 61 L59 39 L70 52 L82 28 L92 48 L107 28 L113 50 L132 38 L131 58 L143 51 L140 84 C122 72 60 72 40 83 Z',
      fill: fills.hair,
    }, 'hm-avatar3d-hair-front hm-avatar3d-hair-spiky');
    addSvg(hair, 'path', {d: 'M53 51 Q82 31 124 50'}, 'hm-avatar3d-hair-shine');

    addSvg(head, 'path', {d: 'M57 77 Q69 69 81 77'}, 'hm-avatar3d-eyebrow hm-avatar3d-eyebrow-left');
    addSvg(head, 'path', {d: 'M99 77 Q111 69 123 77'}, 'hm-avatar3d-eyebrow hm-avatar3d-eyebrow-right');
    buildEye(head, 69, 'left', fills);
    buildEye(head, 111, 'right', fills);
    addSvg(head, 'ellipse', {cx: '57', cy: '111', rx: '10', ry: '5'}, 'hm-avatar3d-cheek');
    addSvg(head, 'ellipse', {cx: '123', cy: '111', rx: '10', ry: '5'}, 'hm-avatar3d-cheek');
    addSvg(head, 'path', {d: 'M88 101 Q84 111 91 113 Q96 112 97 108'}, 'hm-avatar3d-nose');
    addSvg(head, 'circle', {cx: '91', cy: '110', r: '4'}, 'hm-avatar3d-button-nose');

    const mouths = addSvg(head, 'g', {}, 'hm-avatar3d-mouths');
    addSvg(mouths, 'path', {d: 'M76 121 Q90 136 104 121'}, 'hm-avatar3d-mouth hm-avatar3d-mouth-smile');
    addSvg(mouths, 'path', {d: 'M75 121 Q90 139 105 121 Q90 130 75 121 Z'},
      'hm-avatar3d-mouth hm-avatar3d-mouth-grin');
    addSvg(mouths, 'ellipse', {cx: '90', cy: '126', rx: '12', ry: '9'},
      'hm-avatar3d-mouth hm-avatar3d-mouth-open');
    addSvg(mouths, 'path', {d: 'M80 126 Q90 132 100 126'}, 'hm-avatar3d-mouth hm-avatar3d-mouth-calm');
    addSvg(head, 'path', {d: 'M48 101 Q44 92 47 83 M132 101 Q136 92 133 83'},
      'hm-avatar3d-face-rim');
  }

  function starPath(cx, cy, outer, inner) {
    const points = [];
    for (let index = 0; index < 10; index += 1) {
      const radius = index % 2 === 0 ? outer : inner;
      const angle = -Math.PI / 2 + index * Math.PI / 5;
      points.push(`${cx + Math.cos(angle) * radius},${cy + Math.sin(angle) * radius}`);
    }
    return points.join(' ');
  }

  function buildSparkles(svg) {
    const group = addSvg(svg, 'g', {}, 'hm-avatar3d-sparkles');
    [
      [25, 60, 8, 4], [152, 48, 10, 5], [160, 137, 7, 3.5], [22, 142, 6, 3],
    ].forEach((item, index) => {
      addSvg(group, 'polygon', {
        points: starPath(item[0], item[1], item[2], item[3])
      }, `hm-avatar3d-sparkle hm-avatar3d-sparkle-${index + 1}`);
    });
  }

  function hydrateFigure(figure) {
    if (!figure) return figure;
    ensureStylesheet();
    if (figure.getAttribute('data-avatar-renderer') === 'vivid-3d') return figure;
    while (figure.firstChild) figure.removeChild(figure.firstChild);
    figure.classList.add('hm-character-avatar');
    figure.setAttribute('data-character-figure', '');
    figure.setAttribute('data-avatar-renderer', 'vivid-3d');
    figure.setAttribute('aria-hidden', 'true');

    figureSequence += 1;
    const prefix = `hm-avatar3d-${figureSequence}`;
    const canvas = document.createElement('span');
    canvas.className = 'hm-avatar3d-canvas';
    const svg = svgElement('svg', {
      viewBox: '0 0 180 266', preserveAspectRatio: 'xMidYMax meet',
      focusable: 'false', 'aria-hidden': 'true'
    }, 'hm-avatar3d-svg');
    buildDefinitions(svg, prefix);
    addSvg(svg, 'ellipse', {cx: '90', cy: '249', rx: '56', ry: '9'}, 'hm-avatar3d-ground-shadow');
    buildSparkles(svg);
    const rig = addSvg(svg, 'g', {filter: `url(#${prefix}-shadow)`}, 'hm-avatar3d-rig');
    const fills = {
      skin: `url(#${prefix}-skin)`,
      hair: `url(#${prefix}-hair)`,
      outfit: `url(#${prefix}-outfit)`,
      trousers: `url(#${prefix}-trousers)`,
      shoe: `url(#${prefix}-shoe)`,
      rainbowShoe: `url(#${prefix}-rainbow-shoe)`,
      eye: `url(#${prefix}-eye)`,
    };
    buildHair(rig, fills);
    buildLegsAndShoes(rig, fills);
    buildBody(rig, fills);
    buildArms(rig, fills);
    buildFace(rig, fills);
    canvas.appendChild(svg);
    figure.appendChild(canvas);
    return figure;
  }

  function createFigure(extraClass) {
    const figure = document.createElement('span');
    figure.className = `hm-character-avatar ${extraClass || ''}`.trim();
    return hydrateFigure(figure);
  }

  function setGradientStops(figure, prefix, colours) {
    const names = ['light', '', 'shadow'];
    names.forEach((name, index) => {
      const suffix = name ? `-${name}` : '';
      figure.querySelectorAll(`.hm-avatar3d-stop-${prefix}${suffix}`).forEach((stop) => {
        stop.setAttribute('stop-color', colours[index]);
        stop.style.setProperty('stop-color', colours[index]);
      });
    });
  }

  function applyGradientPalettes(figure, profile) {
    const explicitDress = profile.bottoms === 'pink_dress'
      || profile.bottoms === 'purple_dress';
    const matchedDress = profile.bottoms === 'match_outfit'
      && profile.clothes === 'pink_dress';
    const outfitPalette = explicitDress
      ? BOTTOM_PALETTES[profile.bottoms]
      : OUTFIT_PALETTES[profile.clothes];
    const bottomPalette = profile.bottoms === 'match_outfit'
      ? (matchedDress
        ? OUTFIT_PALETTES[profile.clothes]
        : TROUSER_PALETTES[profile.clothes])
      : BOTTOM_PALETTES[profile.bottoms];
    setGradientStops(figure, 'skin', SKIN_PALETTES[profile.skin_tone]);
    setGradientStops(figure, 'hair', HAIR_PALETTES[profile.hair_colour]);
    setGradientStops(figure, 'eye', EYE_PALETTES[profile.eye_colour]);
    setGradientStops(figure, 'outfit', outfitPalette);
    setGradientStops(figure, 'trousers', bottomPalette);
    setGradientStops(figure, 'shoe', SHOE_PALETTES[profile.shoes]);
  }

  function applyEyeGeometry(figure, profile) {
    const isGirl = profile.character === 'girl';
    const whiteWidth = isGirl ? '10.5' : '13';
    const whiteHeight = isGirl
      ? (profile.eye_shape === 'almond' ? '5.8' : '7')
      : (profile.eye_shape === 'almond' ? '7.5' : '10');
    figure.querySelectorAll('.hm-avatar3d-eye-white').forEach((eye) => {
      eye.setAttribute('rx', whiteWidth);
      eye.setAttribute('ry', whiteHeight);
    });
    figure.querySelectorAll('.hm-avatar3d-iris').forEach((iris) => {
      iris.setAttribute('r', isGirl ? '5.2' : '7');
    });
    figure.querySelectorAll('.hm-avatar3d-pupil').forEach((pupil) => {
      pupil.setAttribute('r', isGirl ? '2.6' : '3.5');
    });
    figure.querySelectorAll('.hm-avatar3d-eye-glint').forEach((glint) => {
      glint.setAttribute('r', isGirl ? '1.5' : '2.2');
    });
    figure.querySelectorAll('.hm-avatar3d-eye-glint-small').forEach((glint) => {
      glint.setAttribute('r', isGirl ? '.7' : '1');
    });
  }

  function setProportionTransform(figure, selector, transform) {
    figure.querySelectorAll(selector).forEach((group) => {
      if (transform) group.setAttribute('transform', transform);
      else group.removeAttribute('transform');
    });
  }

  function applyCharacterProportions(figure, profile) {
    const transforms = profile.character === 'girl'
      ? GIRL_PROPORTION_TRANSFORMS : {};
    setProportionTransform(figure, '.hm-avatar3d-proportions-head', transforms.head);
    setProportionTransform(figure, '.hm-avatar3d-proportions-torso', transforms.torso);
    setProportionTransform(figure, '.hm-avatar3d-proportions-lower', transforms.lower);
    setProportionTransform(figure, '.hm-avatar3d-proportions-arm-left', transforms.armLeft);
    setProportionTransform(figure, '.hm-avatar3d-proportions-arm-right', transforms.armRight);
  }

  function applyAppearance(figure, profile, context) {
    if (!figure) return null;
    hydrateFigure(figure);
    const safeProfile = profileCopy(profile);
    const source = context && typeof context === 'object' ? context : {};
    const age = ageDetails(source.age, source.year_group);
    const growth = growthForXp(source.lifetime_xp != null
      ? source.lifetime_xp
      : source.growth && source.growth.lifetime_xp);
    Object.keys(ATTRIBUTES).forEach((group) => {
      figure.setAttribute(ATTRIBUTES[group], safeProfile[group]);
    });
    applyGradientPalettes(figure, safeProfile);
    applyEyeGeometry(figure, safeProfile);
    applyCharacterProportions(figure, safeProfile);
    figure.setAttribute('data-age', String(age.age));
    figure.setAttribute('data-age-stage', String(age.stage));
    figure.setAttribute('data-growth-stage', String(growth.stage));
    const scale = Math.max(0.78, Math.min(1.13,
      age.scale * (XP_SCALES[growth.stage] || 1)));
    figure.style.setProperty('--hm-character-scale', scale.toFixed(3));
    return {profile: safeProfile, age, growth};
  }

  function applyAll(root, profile, context) {
    const scope = root && root.querySelectorAll ? root : document;
    const figures = scope.matches && scope.matches('[data-character-figure]')
      ? [scope] : Array.from(scope.querySelectorAll('[data-character-figure]'));
    let state = null;
    figures.forEach((figure) => {
      state = applyAppearance(figure, profile, context);
    });
    return state;
  }

  function prefersReducedMotion() {
    return Boolean(global.matchMedia
      && global.matchMedia('(prefers-reduced-motion: reduce)').matches);
  }

  function play(figure, action) {
    if (!figure) return;
    const safeAction = ['dance', 'celebrate'].includes(action)
      ? action : 'celebrate';
    const classes = ['is-dancing', 'is-celebrating'];
    const previousTimer = actionTimers.get(figure);
    if (previousTimer) global.clearTimeout(previousTimer);
    classes.forEach((className) => figure.classList.remove(className));
    void figure.offsetWidth;
    figure.classList.add(safeAction === 'dance' ? 'is-dancing' : 'is-celebrating');
    const delay = prefersReducedMotion() ? 220 : 1250;
    actionTimers.set(figure, global.setTimeout(() => {
      classes.forEach((className) => figure.classList.remove(className));
      actionTimers.delete(figure);
    }, delay));
  }

  function playAll(root, action) {
    const scope = root && root.querySelectorAll ? root : document;
    const figures = scope.matches && scope.matches('[data-character-figure]')
      ? [scope] : Array.from(scope.querySelectorAll('[data-character-figure]'));
    figures.forEach((figure) => play(figure, action));
  }

  function enableTilt(container, figure) {
    if (!container || !figure || prefersReducedMotion()) return function noop() {};
    function move(event) {
      if (event.pointerType === 'touch') return;
      const rect = container.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      const x = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
      const y = Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height));
      figure.style.setProperty('--hm-avatar-tilt-y', `${((x - 0.5) * 12).toFixed(2)}deg`);
      figure.style.setProperty('--hm-avatar-tilt-x', `${((0.5 - y) * 8).toFixed(2)}deg`);
    }
    function reset() {
      figure.style.setProperty('--hm-avatar-tilt-y', '0deg');
      figure.style.setProperty('--hm-avatar-tilt-x', '0deg');
    }
    container.addEventListener('pointermove', move);
    container.addEventListener('pointerleave', reset);
    return function cleanup() {
      container.removeEventListener('pointermove', move);
      container.removeEventListener('pointerleave', reset);
    };
  }

  global.HomeworkMagicAvatar = Object.freeze({
    AVATAR_STYLESHEET_PATH,
    ATTRIBUTES,
    CHARACTER_PRESETS,
    DEFAULTS: PROFILE_DEFAULTS,
    OPTIONS,
    XP_STAGES,
    ageDetails,
    applyAll,
    applyAppearance,
    createFigure,
    enableTilt,
    ensureStylesheet,
    growthForXp,
    hydrateFigure,
    normaliseState,
    optionValue,
    play,
    playAll,
    profileCopy,
  });
})(window);
