'use strict';

(function initialiseHomeworkMagicAvatarData(global) {
  if (global.HomeworkMagicAvatarData) return;

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
      {value: 'pink_jumper', label: 'Pink jumper', symbol: '🌸'},
      {value: 'star_jacket', label: 'Star jacket', symbol: '⭐'},
      {value: 'sunshine_dungarees', label: 'Sunshine dungarees', symbol: '☀️'},
      {value: 'pink_vest', label: 'Pink vest', symbol: '🩷'},
      {value: 'blue_vest', label: 'Blue vest', symbol: '💙'},
    ],
    bottoms: [
      {value: 'match_outfit', label: 'Match my outfit', symbol: '✨'},
      {value: 'navy_trousers', label: 'Navy trousers', symbol: '👖'},
      {value: 'blue_jeans', label: 'Blue jeans', symbol: '🔵'},
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
      {value: 'dark_brown', label: 'Dark brown hair', symbol: '●', swatch: '#4a2c1a'},
    {value: 'teal', label: 'Teal hair', symbol: '●', swatch: '#42b8b0'},
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
    dark_brown: ['#8b6345', '#4a2c1a', '#1f0f06'],
    teal: ['#79e0d6', '#42b8b0', '#1e6f70'],
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
    pink_vest: ['#ffb7c7', '#e8687e', '#a83a4c'],
    blue_vest: ['#81c4f0', '#3b82c4', '#1e4d78'],
    pink_jumper: ['#fcc3d5', '#e8749a', '#b84a6c'],
  });
  const TROUSER_PALETTES = Object.freeze({
    purple_hoodie: ['#7b90b5', '#49567e', '#293955'],
    blue_tshirt: ['#6986ad', '#344c72', '#1e2c44'],
    green_jumper: ['#6f9892', '#365f5a', '#1e3e3a'],
    pink_dress: ['#9d84ac', '#685478', '#3d2f49'],
    star_jacket: ['#737b9f', '#3c4365', '#22263e'],
    sunshine_dungarees: ['#7db0d4', '#3f78a7', '#244a69'],
    pink_vest: ['#9d84ac', '#685478', '#3d2f49'],
    blue_vest: ['#6b86ad', '#364d72', '#1e2c44'],
    pink_jumper: ['#9d84ac', '#685478', '#3d2f49'],
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

  global.HomeworkMagicAvatarData = Object.freeze({
    PROFILE_DEFAULTS,
    CHARACTER_PRESETS,
    OPTIONS,
    ATTRIBUTES,
    XP_STAGES,
    AGE_SCALES,
    XP_SCALES,
    GIRL_PROPORTION_TRANSFORMS,
    SKIN_PALETTES,
    HAIR_PALETTES,
    EYE_PALETTES,
    OUTFIT_PALETTES,
    TROUSER_PALETTES,
    BOTTOM_PALETTES,
    SHOE_PALETTES,
  });
})(window);
