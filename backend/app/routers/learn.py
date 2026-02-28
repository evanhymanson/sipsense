"""
SipSense Learn Router

Educational content about whiskey: category guides, distillery stories, and glossary.
Content is embedded directly — no DB or file system required.
"""

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/learn", tags=["learn"])


# ── Category guides ───────────────────────────────────────────────────────────

CATEGORIES = [
    {
        "slug": "bourbon",
        "title": "Bourbon",
        "emoji": "🥃",
        "tagline": "America's native spirit — sweet, warm, and unapologetically approachable",
        "quick_facts": [
            "At least 51% corn in the grain mix",
            "Aged in new charred American oak barrels",
            "Must be produced in the United States",
            "No minimum age requirement (2 years for 'Straight Bourbon')",
        ],
        "flavor_tags": ["vanilla", "caramel", "oak", "sweet", "honey"],
        "body": [
            "What makes bourbon bourbon? Three things: at least 51% corn in the grain mix (the 'mash bill'), aged in new charred American oak barrels, and produced in the United States. That's it. There's no requirement that it come from Kentucky — though 95% of the world's bourbon does.",
            "The magic is what those charred barrels do. When clear, fiery new spirit goes in, the oak acts as both filter and flavor machine. The char layer traps harsh sulfurous compounds while the wood releases vanilla, caramel, brown sugar, and toasty oak. Longer aging means more wood character — but also more risk of over-oaking. The sweet spot for most bourbons is 4 to 12 years.",
            "Bourbon's flavors are defined by two camps: high-rye and wheated. High-rye bourbons (Four Roses, Knob Creek, Bulleit) use rye as a secondary grain, adding spice, complexity, and dryness. Wheated bourbons (Maker's Mark, Pappy Van Winkle, Larceny) swap the rye for softer winter wheat, producing a rounder, sweeter, gentler whiskey. That fork is the first real decision in bourbon exploration.",
            "Kentucky's climate is an unsung hero. Hot summers and cold winters cycle the spirit aggressively in and out of the wood — expanding into the barrel when warm, contracting back when cold — extracting flavor faster than almost anywhere else. Limestone-filtered water low in iron content is also credited for Kentucky's bourbon quality. Geography matters here.",
            "Start with Buffalo Trace or Maker's Mark — both under $30, both benchmarks. Once you know what you like, follow the fork: high-rye or wheated, then up the ladder from there.",
        ],
        "entry_bottles": ["Buffalo Trace", "Maker's Mark", "Woodford Reserve", "Four Roses Yellow Label"],
        "next_explore": "rye",
    },
    {
        "slug": "scotch",
        "title": "Scotch Whisky",
        "emoji": "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
        "tagline": "Five distinct regions, one ancient tradition, infinite complexity",
        "quick_facts": [
            "Must be made and aged in Scotland",
            "Minimum 3 years aging in oak casks",
            "Single malt = one distillery, malted barley only",
            "Blended Scotch mixes malts from multiple distilleries",
        ],
        "flavor_tags": ["fruity", "floral", "smoky", "peaty", "oak", "sherry"],
        "body": [
            "Scotch whisky (note: no 'e') is really five different drinks in one category, each shaped by the Scottish region that produced it. Understanding those regions is the fastest path through the category.",
            "The Lowlands are Scotland's gentlest whiskies — light, floral, approachable, almost grassy. Speyside is a river valley in the northeast that produces more distilleries per square mile than anywhere on earth: Macallan, Glenfiddich, Balvenie, Aberlour. Speyside malts tend toward fruity, elegant, and accessible — the natural entry point for most people. The Highlands are broader and more varied, ranging from light coastal drams to rich, full-bodied, sometimes peaty expressions. Campbeltown is a small peninsula with a briny, maritime character all its own.",
            "Then there's Islay. Pronounced 'Eye-la', this small island off Scotland's western coast produces the world's most polarizing whiskies. Laphroaig, Ardbeg, Lagavulin — intensely smoky, medicinal, briny, peaty. The peat used to dry the barley here has been saturated by the Atlantic for thousands of years. The result tastes like it. You'll either love it immediately or hate it completely, and both are valid responses.",
            "The peat question is the single most important preference to establish early. Most Scotch is unpeated — light, fruity, elegant. Peated Scotch is a completely different experience. Sort out where you stand on smoke before spending money on the premium stuff.",
            "Most Scotch sold globally is blended — whisky from multiple distilleries combined for consistency and scale. Single malts come from a single distillery and tend to have more distinctive characters. Neither is better; they serve different purposes. Start with Glenfiddich 12 or Glenlivet 12 if you want an approachable introduction. The Islay world can wait.",
        ],
        "entry_bottles": ["Glenfiddich 12", "Glenlivet 12", "Monkey Shoulder (blend)", "Aberlour 12"],
        "next_explore": "islay",
    },
    {
        "slug": "rye",
        "title": "Rye Whiskey",
        "emoji": "🌾",
        "tagline": "Bourbon's drier, spicier sibling — complex, assertive, underappreciated",
        "quick_facts": [
            "At least 51% rye grain in the mash bill",
            "American rye rules mirror bourbon rules otherwise",
            "Canadian 'rye' is often NOT majority rye grain — a historical naming tradition",
            "95%+ rye mash bills produce the boldest, spiciest expressions",
        ],
        "flavor_tags": ["spicy", "pepper", "herbal", "dry", "rye bread"],
        "body": [
            "Rye whiskey is what happens when you replace bourbon's sweet corn with spicy, assertive rye grain. The rules are nearly identical to bourbon, but the flavor shift is dramatic. Where bourbon leads with vanilla and caramel warmth, rye leads with pepper, clove, herbal dill, and a dry, lingering finish that refuses to let go.",
            "American rye divides into two camps. Low-rye (55-65% rye grain) still carries some bourbon-like softness — approachable, still sweet, a gentler introduction to the style. High-rye (95%+ rye) is where the character gets assertive and polarizing. Rittenhouse 100, Pikesville, Knob Creek Rye — these are bold, complex whiskeys that reward patience.",
            "The best entry path into rye: start with a spicy bourbon (like Bulleit or Knob Creek) to prime your palate, then move to Bulleit Rye or Rittenhouse 100. Both are under $35, both clearly represent the category, and both will tell you immediately whether rye is your direction.",
            "A word on Canadian whisky: it's long been called 'rye' even though most of it isn't majority-rye grain. In the 1800s, rye was used as a flavoring element in Canadian blends, giving them spice compared to the neutral grain base. The name stuck culturally. Crown Royal, Canadian Club — these are lighter, softer, and sweeter than American rye. Neither is better, but they're very different things wearing the same label.",
            "Cocktails are where rye earns its keep. The Manhattan was originally made with rye, not bourbon, and for good reason — the spirit's dryness and spice stand up to sweet vermouth and bitters in a way that corn-forward bourbon can't always match. If you drink Manhattans and have never tried them with rye, that's today's homework.",
        ],
        "entry_bottles": ["Bulleit Rye", "Rittenhouse 100", "Knob Creek Rye", "Pikesville Straight Rye"],
        "next_explore": "bourbon",
    },
    {
        "slug": "irish",
        "title": "Irish Whiskey",
        "emoji": "☘️",
        "tagline": "The world's most approachable style — smooth by design, not by accident",
        "quick_facts": [
            "Triple distillation produces a lighter, smoother spirit than most whiskeys",
            "Must be aged at least 3 years in wooden casks",
            "Mostly unpeated — smooth and soft, not smoky",
            "'Pure pot still' is a uniquely Irish style made from malted + unmalted barley",
        ],
        "flavor_tags": ["smooth", "light", "fruity", "vanilla", "malty"],
        "body": [
            "Irish whiskey is almost certainly the easiest category to fall in love with, and that smoothness is entirely by design. The defining characteristic is triple distillation — while most whiskeys worldwide are distilled twice, Irish distillers run their spirit through the pot still three times. The extra pass strips out harsh congeners and rough edges, leaving a lighter, cleaner, more approachable spirit. There's a reason Irish whiskey is where many non-whiskey drinkers begin.",
            "The flavor profile tends toward light orchard fruit (green apple, pear), gentle vanilla, soft malt, and sometimes a slightly oily, rounded texture from pot still production. What you won't find is the assertive rye spice of American whiskey or the peaty smoke of Islay Scotch. Irish whiskey is about harmony and approachability.",
            "The uniquely Irish style is 'pure pot still' whiskey, made from a blend of malted and unmalted barley in a copper pot still. This combination produces a slightly spicy, slightly oily, distinctly textured whiskey unlike anything else. Redbreast is the standard-bearer. It's richer, more complex, and more characterful than standard Irish — and it's one of the best whiskeys at any price.",
            "The market is dominated by Jameson, and for good reason — it's consistent, inoffensive, widely available, and performs exactly the role an entry-level Irish whiskey should. It introduced millions of people to the category. But if Jameson is where you are, Jameson Black Barrel (richer, double-casked) or Redbreast 12 (pot still, genuinely complex) are natural next steps that will show you how far the category goes.",
            "Ireland once had hundreds of distilleries and dominated world whiskey production. A combination of independence, Prohibition cutting off American exports, and trade disputes nearly destroyed the industry. By the 1970s, a handful of distilleries remained. The category's revival — now with dozens of new craft distilleries opening across the island — is one of the better stories in modern spirits.",
        ],
        "entry_bottles": ["Jameson", "Redbreast 12", "Green Spot", "Teeling Single Malt"],
        "next_explore": "japanese",
    },
    {
        "slug": "japanese",
        "title": "Japanese Whisky",
        "emoji": "🗾",
        "tagline": "Precision, restraint, and balance taken to their logical extreme",
        "quick_facts": [
            "Japanese distillers learned directly from Scotland in the 1920s",
            "Defined by harmony and balance rather than boldness",
            "Often expensive due to genuine rarity and international demand",
            "Mizunara oak casks give some expressions a unique incense-like character",
        ],
        "flavor_tags": ["delicate", "floral", "fruity", "clean", "balanced"],
        "body": [
            "Japanese whisky is one of the great success stories of the 20th century. It started with Masataka Taketsuru, a young Japanese chemist who went to Scotland in 1918, apprenticed at traditional distilleries, and married a Scottish woman. He brought both back to Japan. Together with Shinjiro Torii, founder of Suntory, they built what is now one of the most awarded whisky traditions in the world.",
            "What makes Japanese whisky distinctive isn't just technique — it's philosophy. Where Islay Scotch wears its intensity on its sleeve, Japanese whisky is about restraint: nothing too loud, everything in service of harmony and balance. The flavors are there — floral blossom, orchard fruit, vanilla, sometimes a whisper of smoke — but they're in conversation with each other rather than competing.",
            "Japanese distilleries tend to be extraordinarily self-sufficient. Because there's no Scottish tradition of distilleries trading whisky stocks with each other, Japanese distillers make everything in-house: different pot still shapes, different yeast strains, different cask types, all under one roof. This internal complexity is then blended into expressions of remarkable consistency.",
            "The famous names: Suntory's Yamazaki (single malt, Japan's first distillery), Hakushu (high-altitude forest distillery, lighter and herbal), and the legendary Hibiki blended whisky. Nikka's Yoichi (coastal, heavier) and Miyagikyo (delicate, fruity) round out the essential range. Each is genuinely excellent. Each is also genuinely expensive.",
            "The price is real. Japanese whisky's global popularity — particularly the 2014 moment when Yamazaki Sherry Cask won World Whisky of the Year — created demand that outstripped decades of aging stock. Bottles that were $40 in 2010 are now $120. Some shortages are real; some are manufactured. But the quality at the top end is undeniable, and entry-level expressions like Toki or Nikka From the Barrel still offer exceptional value relative to the experience.",
        ],
        "entry_bottles": ["Suntory Toki", "Nikka From the Barrel", "Yamazaki 12", "Hakushu 12"],
        "next_explore": "scotch",
    },
    {
        "slug": "canadian",
        "title": "Canadian Whisky",
        "emoji": "🍁",
        "tagline": "The most underrated category in whisky — and quietly having a renaissance",
        "quick_facts": [
            "Defined by blending multiple grain distillates for balanced flavor",
            "Called 'rye' by tradition, even when actual rye content is low",
            "Must be aged at least 3 years in Canada",
            "Lighter and more versatile than most other whisky styles",
        ],
        "flavor_tags": ["light", "smooth", "vanilla", "caramel", "gentle spice"],
        "body": [
            "Canadian whisky is the most underrated category in the world. Decades of being known as 'light blended stuff for mixing' have buried what Canadian distillers can actually produce — and a quiet renaissance of craft distilling is changing the story.",
            "The style is defined by blending. Canadian producers distill from multiple grains — corn, rye, wheat, barley — separately, to different proofs and flavor profiles. The lighter grain base spirit provides volume and smoothness; the more characterful 'flavoring whisky' (traditionally rye-heavy) provides complexity and spice. These are then blended in proportions to achieve the house style.",
            "The 'rye' label is cultural, not necessarily literal. In the 1800s, rye grain gave Canadian blends a distinctive spice compared to the neutral base spirit, and the name stuck. Modern Canadian 'rye' might have very little actual rye grain. Crown Royal, Canadian Club — both lighter and softer than American rye whiskey, despite the name.",
            "Where it gets genuinely exciting: premium Canadian expressions that embrace the rye identity seriously. Crown Royal Northern Harvest Rye won World Whisky of the Year in 2016, shocking the industry. Lot No. 40, Alberta Premium Cask Strength, and the output from newer craft distilleries demonstrate the category's ceiling is much higher than its reputation suggests.",
            "The Canadian angle is almost always value. Quality is high, prices are reasonable, and the craft scene is expanding. If you're a bourbon or American rye drinker who's never explored Canadian whisky beyond the well pour, the premium tier offers serious quality at below-premium prices.",
        ],
        "entry_bottles": ["Crown Royal Northern Harvest Rye", "Lot No. 40", "Canadian Club 100% Rye", "Pikesville (US-made, influenced by Canadian style)"],
        "next_explore": "rye",
    },
]


# ── Distillery stories ────────────────────────────────────────────────────────

DISTILLERIES = [
    {
        "slug": "makers-mark",
        "title": "Maker's Mark",
        "location": "Loretto, Kentucky",
        "category": "Bourbon",
        "emoji": "🥃",
        "tagline": "The bourbon that proved gentle could be great",
        "known_for": ["Wheated mash bill", "Hand-dipped red wax", "Star Hill Farm"],
        "body": [
            "In 1953, Bill Samuels Sr. did something unusual: he burned his family's 170-year-old bourbon recipe. He wanted a bourbon his wife would actually enjoy drinking — something soft and smooth rather than the harsh, rye-forward whiskeys of the era.",
            "The result was Maker's Mark. By replacing the traditional rye grain with soft winter wheat, Samuels created a 'wheated' bourbon: caramel sweetness up front, vanilla warmth throughout, a soft round finish with no sharp edges. His wife Margie named it after the pewter-maker's marks she collected as a hobby, designed the bottle, and started dipping each one in red sealing wax by hand. That wax-dipped silhouette became one of the most recognized in the spirits world.",
            "The distillery — Star Hill Farm in Loretto, Kentucky — is a National Historic Landmark. Every bottle is still hand-dipped. When supply tightened in 2013 and the company briefly considered reducing alcohol content to stretch inventory, the backlash from loyal customers was so fierce they reversed the decision within days. It's that kind of brand.",
        ],
    },
    {
        "slug": "buffalo-trace",
        "title": "Buffalo Trace",
        "location": "Frankfort, Kentucky",
        "category": "Bourbon",
        "emoji": "🥃",
        "tagline": "The oldest distillery in Kentucky — and home to the most sought-after bottles in bourbon",
        "known_for": ["Pappy Van Winkle", "Eagle Rare", "George T. Stagg", "Antique Collection"],
        "body": [
            "Buffalo Trace Distillery in Frankfort, Kentucky has been making whiskey — by some accounts — since 1787, surviving Prohibition by operating as a 'medicinal whiskey' facility. It's one of the oldest continuously operating distilleries in America, and arguably the most famous address in bourbon.",
            "It's also home to the most allocated, sought-after bottles in the world. The Pappy Van Winkle family of bourbons. Eagle Rare 17-Year. George T. Stagg barrel-proof. William Larue Weller. These are whiskeys people wait years for, pay hundreds of dollars for on the secondary market, and sometimes camp outside liquor stores in the early morning cold for. The distillery's annual 'Antique Collection' release has become a cultural event.",
            "Here's the thing: the everyday Buffalo Trace bourbon — the one with the bison on the label, under $30 at most stores — uses the same mash bill as some of those legendary bottles. It's just younger. It's also one of the best values in bourbon, a benchmark of what well-made Kentucky whiskey tastes like. If you want to understand the category, start here.",
        ],
    },
    {
        "slug": "glenfiddich",
        "title": "Glenfiddich",
        "location": "Dufftown, Speyside, Scotland",
        "category": "Scotch",
        "emoji": "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
        "tagline": "The distillery that invented the idea of single malt as a product category",
        "known_for": ["World's best-selling single malt", "Pioneered the single malt category", "Family-owned since 1887"],
        "body": [
            "Glenfiddich ('Valley of the Deer' in Scottish Gaelic) was founded in 1887 by William Grant in the Speyside region. For most of the 20th century it was the world's best-selling single malt Scotch whisky. In many years it still is.",
            "That success is partly due to strategy and partly due to quality. In the 1960s, when blended Scotch utterly dominated the market, Glenfiddich pioneered the concept of selling single malt as a premium product category in its own right. It was a counterintuitive move at the time. It changed the industry.",
            "The 12-year expression is the textbook Speyside malt: fresh pear, subtle oak, a hint of floral blossom, gentle vanilla. It's not flashy. It's not particularly complex. It's the bourbon of Scotch — a perfect starting point that never offends and rarely disappoints. The distillery is still family-owned by William Grant & Sons, unusual at this scale, and they've maintained production values while expanding into experimental expressions and unusual cask finishes.",
        ],
    },
    {
        "slug": "laphroaig",
        "title": "Laphroaig",
        "location": "Islay, Scotland",
        "category": "Scotch",
        "emoji": "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
        "tagline": "The most polarizing whisky on Earth — and proud of it",
        "known_for": ["Intensely peated", "Royal Warrant from Prince Charles", "Friends of Laphroaig fan club"],
        "body": [
            "Laphroaig (pronounced 'La-FROYG') is the whisky that most divides opinion. People who love it really love it — including Prince Charles, who granted it a Royal Warrant of Appointment. People who don't love it say it smells like a hospital fire at the beach. Both descriptions are technically accurate.",
            "The reason is peat. Laphroaig's barley is dried over burning Islay peat cut from the distillery's own bog — a bog that has been soaked in seawater for thousands of years. The result is a whisky that carries smoke, seaweed, iodine, antiseptic, and the cold grey Atlantic in every dram. It's one of the least subtle things you'll ever taste.",
            "Founded in 1815 on the southern coast of Islay, Laphroaig was one of the first legal distilleries on the island. The 10-year expression is the canonical Islay whisky, and one of the most instructive bottles in the category: it will tell you, immediately and definitively, whether the peated world is for you. Friends of Laphroaig — one of the whisky world's oldest fan clubs — grants members a lifetime lease on a square foot of Islay peat bog and a small dram when they visit to collect their 'rent.'",
        ],
    },
    {
        "slug": "ardbeg",
        "title": "Ardbeg",
        "location": "Port Ellen, Islay, Scotland",
        "category": "Scotch",
        "emoji": "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
        "tagline": "Where peat fanatics go when Laphroaig isn't enough",
        "known_for": ["Highest peat levels of any major distillery", "Cult annual releases", "One of the world's most awarded whiskies"],
        "body": [
            "If Laphroaig is the entry point to Islay peat, Ardbeg is where the obsession deepens. The distillery on the southeast coast of Islay produces whisky at around 55 ppm phenols — among the highest peat levels of any major distillery in the world. This is not subtle.",
            "What makes Ardbeg special beyond the smoke is its complexity. The peat is there — campfire, tar, sea brine — but underneath it are layers of dark chocolate, vanilla, citrus oil, and coastal wildness that keep revealing themselves over time. It's not one-dimensional heat; it's an evolving conversation in your glass.",
            "The distillery was closed multiple times in the 20th century due to financial difficulties, finally rescued in 1997. The annual Ardbeg Day limited releases and Ardbeg Committee bottlings have built one of the most dedicated fanbases in the whisky world. The standard 10-year expression is consistently one of the highest-rated whiskies at its price point, year after year, from every major publication. For peat lovers, it's non-negotiable.",
        ],
    },
    {
        "slug": "macallan",
        "title": "The Macallan",
        "location": "Craigellachie, Speyside, Scotland",
        "category": "Scotch",
        "emoji": "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
        "tagline": "Scotch whisky's luxury brand — sherry casks, deep color, and stratospheric ambition",
        "known_for": ["Sherry cask maturation", "Record-breaking auction prices", "The Easter Elchies estate"],
        "body": [
            "The Macallan is Scotch whisky's closest equivalent to a luxury fashion house. Based in Speyside on the Easter Elchies estate, it's defined by two things: exceptional sherry-cask maturation and a price ladder that extends into the stratosphere.",
            "The sherry cask commitment is genuine and distinctive. While most distilleries use ex-bourbon barrels for the majority of their whisky, Macallan traditionally ages a large proportion in expensive Oloroso sherry casks from Jerez, Spain. These casks give the spirit rich dried fruit notes — raisin, fig, dark chocolate, orange peel — along with deep mahogany color and weight. The result is one of the most recognizable house styles in Scotch.",
            "At the entry level, the 12-Year Double Cask is excellent and accessible — honeyed, rich, and sherry-forward. At the high end, Macallan becomes trophy whisky: aged expressions in the thousands of dollars, and single bottles that regularly break auction records. A Valerio Adami 1926 Macallan sold for $1.5 million at Christie's in 2019. The point at which the liquid's quality and the bottle's status diverge is left as an exercise for the buyer.",
        ],
    },
    {
        "slug": "yamazaki",
        "title": "Yamazaki",
        "location": "Shimamoto, Osaka Prefecture, Japan",
        "category": "Japanese Whisky",
        "emoji": "🗾",
        "tagline": "Japan's first distillery — and the bottle that changed everything",
        "known_for": ["Japan's first whisky distillery (1923)", "Yamazaki 18 — one of the world's most awarded whiskies", "Mizunara oak cask expressions"],
        "body": [
            "The Yamazaki distillery was built in 1923 in a misty bamboo valley outside Osaka, at the confluence of three rivers — a location chosen for its pure water. It was Japan's first whisky distillery. Its founder, Shinjiro Torii, had already built a successful wine importing business when he decided Japan needed its own whisky. He hired Masataka Taketsuru, who had just returned from studying Scotch production in Scotland, and together they built something genuinely new.",
            "Yamazaki produces single malt in a remarkable variety of styles internally — different pot still shapes, yeast strains, and cask types including the rare Japanese Mizunara oak, which gives a distinctive sandalwood and incense character impossible to replicate elsewhere. These are blended into expressions of exceptional balance.",
            "The distillery became internationally famous in 2014 when the Yamazaki Sherry Cask 2013 won World Whisky of the Year — the first time a Japanese whisky claimed the title. Demand immediately outpaced supply, and prices have never returned to pre-2014 levels. The 12-year expression remains one of the finest single malts at its price point: elegant tropical fruit, honey, gentle spice, and that distinctive Japanese precision.",
        ],
    },
    {
        "slug": "jameson",
        "title": "Jameson",
        "location": "Midleton, County Cork, Ireland",
        "category": "Irish Whiskey",
        "emoji": "☘️",
        "tagline": "The whiskey that rebuilt an entire industry from the ground up",
        "known_for": ["World's best-selling Irish whiskey", "Triple distillation", "Rebuilt the Irish whiskey category"],
        "body": [
            "Jameson is the reason Irish whiskey exists in your local bar. Before the brand's global expansion in the 1990s and 2000s, Irish whiskey was nearly dead as a category — reduced from hundreds of distilleries in the 1800s to a handful by the mid-20th century. A combination of independence, Prohibition cutting off American exports, and trade disputes with Britain had devastated the industry.",
            "Jameson's recovery strategy, centered on Irish pubs worldwide and an approachable, universally likable product, rebuilt the category from the ground up. It introduced tens of millions of people to Irish whiskey who would never have tried it otherwise.",
            "The whiskey itself: triple-distilled, blended (grain whiskey plus pot still whiskey), aged at least four years, light and smooth with a whisper of vanilla and green apple. It's not complex, and that's exactly the point. If Jameson is where you are, the natural next steps are Jameson Black Barrel (sweeter, double-casked, noticeably richer) or Redbreast 12 (pure pot still, genuinely complex). Both will show you how far the Irish whiskey category goes beyond its most famous representative.",
        ],
    },
    {
        "slug": "wild-turkey",
        "title": "Wild Turkey",
        "location": "Lawrenceburg, Kentucky",
        "category": "Bourbon",
        "emoji": "🥃",
        "tagline": "101 proof, no apologies, same recipe since 1954",
        "known_for": ["Jimmy Russell — longest-serving active Master Distiller in history", "Wild Turkey 101", "High-rye mash bill"],
        "body": [
            "Wild Turkey doesn't try to be elegant. It's a bourbon with a point of view: bold, high-rye character at 101 proof that earned the name 'Wild' and has never looked back.",
            "Jimmy Russell has been the Master Distiller at Wild Turkey since 1954. His son Eddie joined in 1981. Together they are the longest-serving father-son distilling team in the history of American whiskey. Jimmy has said he's never changed his recipe. He has no plans to.",
            "The high proof is deliberate. When bourbon is diluted from barrel proof to bottling strength, you lose some of the wood and grain character. Wild Turkey 101 is bottled higher to ensure rich caramel, assertive rye spice, and bold oak notes survive the dilution. It's a working bourbon in the best sense — unpretentious, consistent, inexpensive, always good. The rare premium expressions (Rare Breed, Master's Keep) demonstrate the distillery's ceiling. But the $25 bottle of 101 has been one of the best values in bourbon for seventy years.",
        ],
    },
    {
        "slug": "four-roses",
        "title": "Four Roses",
        "location": "Lawrenceburg, Kentucky",
        "category": "Bourbon",
        "emoji": "🥃",
        "tagline": "The most interesting distillery in Kentucky, and most people don't know why",
        "known_for": ["10 distinct bourbon recipes", "Two mash bills × five yeast strains", "Single Barrel and Small Batch expressions"],
        "body": [
            "Four Roses is the most technically fascinating distillery in Kentucky. Here's why: they make 10 different bourbon recipes. Using two mash bills (one standard, one high-rye at 35% rye grain) and five separate proprietary yeast strains — each with a distinct flavor personality — Four Roses produces 10 distinct bourbons, which are blended in different combinations for different expressions.",
            "No other major Kentucky distillery operates this way. Most use one, maybe two recipes. Four Roses' internal complexity is enormous, and it's entirely in service of blending nuance. Each yeast strain contributes something different: one adds floral notes, one adds spice, one adds fruitiness. Understanding this system is like understanding bourbon's grammar.",
            "The entry-level Four Roses Yellow Label is well-balanced and accessible. The Small Batch and Small Batch Select are where it gets genuinely compelling — nuanced, layered, showing the full range of those yeast characters in harmony. The Single Barrel expressions let you taste each of the 10 individual recipes in isolation, a unique educational experience in the category.",
        ],
    },
    {
        "slug": "redbreast",
        "title": "Redbreast",
        "location": "Midleton, County Cork, Ireland",
        "category": "Irish Whiskey",
        "emoji": "☘️",
        "tagline": "The purest expression of Irish pot still whiskey — rich, complex, deeply satisfying",
        "known_for": ["Pure pot still style", "Malted + unmalted barley", "One of the world's most awarded Irish whiskies"],
        "body": [
            "Redbreast is what happens when Irish whiskey stops trying to be approachable and starts trying to be excellent. It's the standard-bearer of 'pure pot still' Irish whiskey, a style unique to Ireland that uses a blend of malted and unmalted barley distilled in a copper pot still.",
            "That combination — malted and unmalted barley — produces something distinctive: a slightly oily, richly textured whiskey with a spiciness and weight that sets it apart from the lighter triple-distilled blends that dominate Irish whiskey shelves. There's dried fruit from sherry cask maturation, nutty complexity, a creamy mouthfeel, and a long, warming finish.",
            "The 12-year is the entry point and it's genuinely exceptional — not just 'good for Irish whiskey' but good by any standard. The 15-year adds more sherry influence and dried fruit complexity. If you've only experienced Irish whiskey through Jameson or Bushmills, Redbreast 12 will reset your expectations for what the category can be.",
        ],
    },
]


# ── Glossary (reused from agent.py vocabulary, extended) ─────────────────────

GLOSSARY = [
    {"term": "Single Malt", "definition": "Whisky made at a single distillery from malted barley only, distilled in pot stills. The 'single' refers to the distillery, not the cask."},
    {"term": "Blended Whisky", "definition": "A mix of grain whisky and one or more malt whiskies from different distilleries, blended for consistency, smoothness, and scale. Most Scotch sold globally is blended."},
    {"term": "Cask Strength", "definition": "Bottled directly from the barrel without dilution, typically 55–65% ABV. More intense, more concentrated, and usually more complex. Always add a few drops of water."},
    {"term": "NAS (Non-Age Statement)", "definition": "No age stated on the label. The whisky may contain younger spirit. Not necessarily lower quality — many excellent whiskies are NAS — but less transparency."},
    {"term": "Peated", "definition": "Made with barley dried over burning peat — partially decomposed vegetation. The smoke infuses the grain with earthy, medicinal, sometimes coastal character. Islay is the center of the peated world."},
    {"term": "Mash Bill", "definition": "The grain recipe used to make whiskey. Bourbon must be at least 51% corn. Rye must be at least 51% rye. The remaining grains shape the secondary flavor profile."},
    {"term": "Maturation", "definition": "The aging process in oak casks where clear, harsh new spirit gains color, complexity, and flavor. Most experts say the barrel contributes 60–70% of a whisky's final character."},
    {"term": "Angel's Share", "definition": "The ~2% of whisky that evaporates through the barrel staves each year during aging. A 20-year Scotch loses roughly a third of its volume to the angels."},
    {"term": "Finish", "definition": "The taste and sensation that linger in your mouth after swallowing. A long, complex finish is a sign of quality. Short or harsh finishes suggest young or lower-quality spirit."},
    {"term": "Nose", "definition": "The aromas detected when smelling whisky in the glass. Serious tasters spend more time nosing than drinking. Try adding a drop of water — it opens up the nose significantly."},
    {"term": "Dram", "definition": "A small measure of whisky, typically 25–50ml. Scottish in origin. The correct answer to 'would you like a dram?' is always yes."},
    {"term": "ABV", "definition": "Alcohol By Volume — the percentage of ethanol in the liquid. Standard bottlings are 40–46%. Cask strength is 55–65%. Barrel proof can go above 70%."},
    {"term": "Expression", "definition": "A specific bottling from a distillery. The Glenfiddich 12-year and Glenfiddich 18-year are two different expressions from the same distillery."},
    {"term": "Age Statement", "definition": "The number on the label showing the age of the youngest whisky in the bottle. A 12-year Scotch spent at least 12 years in oak casks."},
    {"term": "Pot Still", "definition": "Traditional copper kettle used for batch distillation. Creates a heavier, more textured, more flavorful spirit. Used for single malts, Irish pot still whiskey, and craft spirits."},
    {"term": "Column Still", "definition": "A tall continuous distillation apparatus that produces a lighter, higher-proof spirit more efficiently. Used for grain whisky, neutral spirits, and blending base."},
    {"term": "Straight Bourbon", "definition": "Bourbon aged at least 2 years in new charred oak. If aged less than 4 years, it must carry an age statement. Most premium bourbons are 'straight.'"},
    {"term": "Wheated Bourbon", "definition": "Bourbon where wheat replaces rye as the secondary grain. Produces a softer, rounder, sweeter flavor profile. Maker's Mark and the Weller family are the classics."},
    {"term": "Bottled in Bond", "definition": "A US government designation meaning: at least 4 years old, 100 proof, from a single distillery, single distillation season. A reliable quality indicator created in 1897."},
    {"term": "Single Cask", "definition": "Whisky from a single barrel, undiluted and unblended. Every single cask bottling is unique — once the barrel is gone, that exact whisky is gone."},
    {"term": "Speyside", "definition": "Scottish whisky region along the River Spey, producing more distilleries per square mile than anywhere on earth. Home to Macallan, Glenfiddich, Balvenie. Tends toward fruity and elegant."},
    {"term": "Islay", "definition": "A small Scottish island producing the world's most intensely peated whiskies. Laphroaig, Ardbeg, Lagavulin, Bowmore. The peat here has been saturated by the Atlantic Ocean."},
    {"term": "Highlands", "definition": "Scotland's largest whisky region, producing a huge range of styles from light and coastal to rich and peaty. No single defining character — every distillery does something different."},
    {"term": "Lowlands", "definition": "Scotland's gentlest whisky region: light, floral, soft, often triple-distilled like Irish whiskey. Great introduction to Scotch before tackling more complex styles."},
    {"term": "Campbeltown", "definition": "A small peninsula in Scotland with only a handful of distilleries but a distinctive briny, maritime, sometimes slightly oily character all its own."},
    {"term": "Pure Pot Still", "definition": "A uniquely Irish whiskey style made from a mix of malted and unmalted barley in a copper pot still. Produces a richer, slightly oily, more complex spirit. Redbreast is the benchmark."},
    {"term": "Mizunara Oak", "definition": "Rare Japanese oak used for whisky casks. Grows slowly, is difficult to work, and leaks more than American or European oak. But it gives whisky a distinctive sandalwood and incense character found nowhere else."},
    {"term": "PPM (Parts Per Million)", "definition": "The measurement for peat smoke in whisky, specifically phenol content in the malted barley. Unpeated Scotch: 0-2 ppm. Lightly peated: 10-20 ppm. Heavily peated: 50+ ppm. Octomore: 300+ ppm."},
    {"term": "Sherry Cask", "definition": "A barrel previously used to age Oloroso or Pedro Ximénez sherry. Gives whisky rich dried fruit, dark chocolate, and raisin notes, plus deep amber color. Macallan and GlenDronach are famous for heavy sherry influence."},
    {"term": "Solera", "definition": "A blending system where new whisky is added to a vessel that always retains a portion of older whisky. Used by Glenfiddich for their 15-year and some other producers. Produces consistent flavor by always including aged stock."},
]


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/categories")
def list_categories():
    return [
        {
            "slug": c["slug"],
            "title": c["title"],
            "emoji": c["emoji"],
            "tagline": c["tagline"],
            "flavor_tags": c["flavor_tags"],
        }
        for c in CATEGORIES
    ]


@router.get("/categories/{slug}")
def get_category(slug: str):
    cat = next((c for c in CATEGORIES if c["slug"] == slug), None)
    if not cat:
        raise HTTPException(status_code=404, detail=f"Category '{slug}' not found")
    return cat


@router.get("/distilleries")
def list_distilleries():
    return [
        {
            "slug": d["slug"],
            "title": d["title"],
            "location": d["location"],
            "category": d["category"],
            "emoji": d["emoji"],
            "tagline": d["tagline"],
        }
        for d in DISTILLERIES
    ]


@router.get("/distilleries/{slug}")
def get_distillery(slug: str):
    dist = next((d for d in DISTILLERIES if d["slug"] == slug), None)
    if not dist:
        raise HTTPException(status_code=404, detail=f"Distillery '{slug}' not found")
    return dist


@router.get("/glossary")
def get_glossary():
    return sorted(GLOSSARY, key=lambda x: x["term"])
