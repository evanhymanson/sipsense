// 3-level flavor taxonomy: family → subfamily → specific note
// Each `id` is used as the ?flavor= query param, matched against the
// comma-separated flavor_profile field in the DB via substring search.

export const FLAVOR_TAXONOMY = [
  {
    id: 'smoky',
    label: 'Smoky',
    color: '#4b5563',
    children: [
      {
        id: 'peaty',
        label: 'Peaty',
        children: [
          { id: 'medicinal', label: 'Medicinal' },
          { id: 'mossy',     label: 'Mossy' },
          { id: 'bonfire',   label: 'Bonfire' },
        ],
      },
      {
        id: 'ashy',
        label: 'Ashy',
        children: [
          { id: 'charcoal',  label: 'Charcoal' },
          { id: 'gunpowder', label: 'Gunpowder' },
        ],
      },
    ],
  },
  {
    id: 'sweet',
    label: 'Sweet',
    color: '#b45309',
    children: [
      {
        id: 'caramel',
        label: 'Caramel',
        children: [
          { id: 'toffee',       label: 'Toffee' },
          { id: 'butterscotch', label: 'Butterscotch' },
          { id: 'brown sugar',  label: 'Brown Sugar' },
        ],
      },
      {
        id: 'vanilla',
        label: 'Vanilla',
        children: [
          { id: 'cream',   label: 'Cream' },
          { id: 'custard', label: 'Custard' },
        ],
      },
      {
        id: 'honey',
        label: 'Honey',
        children: [
          { id: 'heather', label: 'Heather' },
          { id: 'beeswax', label: 'Beeswax' },
        ],
      },
    ],
  },
  {
    id: 'fruity',
    label: 'Fruity',
    color: '#be185d',
    children: [
      {
        id: 'dark fruit',
        label: 'Dark Fruit',
        children: [
          { id: 'cherry', label: 'Cherry' },
          { id: 'plum',   label: 'Plum' },
          { id: 'raisin', label: 'Raisin' },
        ],
      },
      {
        id: 'citrus',
        label: 'Citrus',
        children: [
          { id: 'orange', label: 'Orange' },
          { id: 'lemon',  label: 'Lemon' },
        ],
      },
      {
        id: 'orchard',
        label: 'Orchard',
        children: [
          { id: 'apple', label: 'Apple' },
          { id: 'pear',  label: 'Pear' },
        ],
      },
      {
        id: 'tropical',
        label: 'Tropical',
        children: [
          { id: 'banana', label: 'Banana' },
          { id: 'mango',  label: 'Mango' },
        ],
      },
    ],
  },
  {
    id: 'spicy',
    label: 'Spicy',
    color: '#c2410c',
    children: [
      {
        id: 'pepper',
        label: 'Pepper',
        children: [
          { id: 'black pepper', label: 'Black Pepper' },
          { id: 'white pepper', label: 'White Pepper' },
          { id: 'chili',        label: 'Chili' },
        ],
      },
      {
        id: 'baking spice',
        label: 'Baking Spice',
        children: [
          { id: 'cinnamon', label: 'Cinnamon' },
          { id: 'nutmeg',   label: 'Nutmeg' },
          { id: 'clove',    label: 'Clove' },
        ],
      },
      {
        id: 'herbal',
        label: 'Herbal',
        children: [
          { id: 'mint',  label: 'Mint' },
          { id: 'anise', label: 'Anise' },
        ],
      },
    ],
  },
  {
    id: 'woody',
    label: 'Woody',
    color: '#7c2d12',
    children: [
      {
        id: 'oak',
        label: 'Oak',
        children: [
          { id: 'cedar',  label: 'Cedar' },
          { id: 'resin',  label: 'Resin' },
        ],
      },
      {
        id: 'earthy',
        label: 'Earthy',
        children: [
          { id: 'leather',  label: 'Leather' },
          { id: 'tobacco',  label: 'Tobacco' },
          { id: 'mushroom', label: 'Mushroom' },
        ],
      },
      {
        id: 'roasted',
        label: 'Roasted',
        children: [
          { id: 'coffee',    label: 'Coffee' },
          { id: 'chocolate', label: 'Chocolate' },
          { id: 'charred',   label: 'Charred' },
        ],
      },
    ],
  },
  {
    id: 'floral',
    label: 'Floral',
    color: '#6d28d9',
    children: [
      {
        id: 'light floral',
        label: 'Light Floral',
        children: [
          { id: 'rose',     label: 'Rose' },
          { id: 'lavender', label: 'Lavender' },
          { id: 'jasmine',  label: 'Jasmine' },
        ],
      },
      {
        id: 'delicate',
        label: 'Delicate',
        children: [
          { id: 'elderflower', label: 'Elderflower' },
          { id: 'chamomile',   label: 'Chamomile' },
        ],
      },
    ],
  },
  {
    id: 'grainy',
    label: 'Grainy',
    color: '#a16207',
    children: [
      {
        id: 'cereal',
        label: 'Cereal',
        children: [
          { id: 'malt',    label: 'Malt' },
          { id: 'corn',    label: 'Corn' },
          { id: 'biscuit', label: 'Biscuit' },
        ],
      },
      {
        id: 'nutty',
        label: 'Nutty',
        children: [
          { id: 'almond',   label: 'Almond' },
          { id: 'walnut',   label: 'Walnut' },
          { id: 'hazelnut', label: 'Hazelnut' },
        ],
      },
    ],
  },
]
