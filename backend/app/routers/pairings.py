"""
Food pairings & cocktail suggestions for whiskeys.

Uses a rule-based mapping for instant results, with optional AI enhancement.
"""

import re
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import models
from ..database import get_db
from ..storage import get_pairing_set, get_cocktail_set, make_cdn_url


def _slugify(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def _with_images(items: list[dict]) -> list[dict]:
    """Add image_url to each pairing item if the image exists."""
    pairing_files = get_pairing_set()
    result = []
    for item in items:
        slug = _slugify(item["item"])
        filename = f"{slug}.jpg"
        img_url = make_cdn_url(f"/uploads/pairings/{filename}") if filename in pairing_files else None
        result.append({**item, "image_url": img_url})
    return result


def _cocktails_with_images(items: list[dict]) -> list[dict]:
    """Add image_url to each cocktail item if the image exists."""
    cocktail_files = get_cocktail_set()
    result = []
    for item in items:
        slug = _slugify(item["name"])
        filename = f"{slug}.jpg"
        img_url = make_cdn_url(f"/uploads/cocktails/{filename}") if filename in cocktail_files else None
        result.append({**item, "image_url": img_url})
    return result

router = APIRouter(prefix="/pairings", tags=["pairings"])

# ── Static pairing rules by category / flavor ───────────────────────────

_FOOD_BY_CATEGORY = {
    "bourbon": [
        {"item": "Smoked BBQ Brisket", "why": "The char and sweetness of bourbon complement smoky meat perfectly — a cornerstone of American whiskey culture"},
        {"item": "Pecan Pie", "why": "Nutty sweetness and toasted caramel echo bourbon's corn-forward richness and vanilla-oak barrel notes"},
        {"item": "Aged Cheddar", "why": "Sharp, crumbly cheese creates a savory-sweet contrast that highlights bourbon's caramel and butterscotch"},
        {"item": "Fried Chicken", "why": "Crispy, salty skin and juicy meat cut through bourbon's sweetness while the fat carries its oak flavors"},
        {"item": "Pulled Pork Sliders", "why": "Sweet, tangy BBQ sauce on tender pork mirrors bourbon's molasses and brown sugar character"},
        {"item": "Gouda (Aged)", "why": "Caramelized, butterscotch-like aged Gouda is almost tailor-made for bourbon's vanilla and toffee notes"},
        {"item": "Pimento Cheese", "why": "A Southern classic — the creamy, tangy, peppery spread bridges bourbon's sweetness and spice"},
        {"item": "Dark Chocolate", "why": "Cocoa bitterness and vanilla notes mirror bourbon's caramel-oak character and provide a clean finish"},
        {"item": "Bread Pudding with Caramel Sauce", "why": "Warm custard and caramel amplify bourbon's baking spice and vanilla in a decadent echo"},
        {"item": "Bananas Foster", "why": "Caramelized bananas and brown sugar flame with bourbon — literally and figuratively a perfect match"},
        {"item": "Cornbread with Honey Butter", "why": "Corn meets corn — the grain-forward sweetness creates a beautiful bridge to bourbon's mash bill"},
        {"item": "Glazed Bacon", "why": "Sweet-salty-smoky bacon hits every note that bourbon's palate craves, an addictive combination"},
    ],
    "scotch": [
        {"item": "Smoked Salmon", "why": "Smoke meets smoke — a time-honored Scottish pairing where the oily fish softens peaty intensity"},
        {"item": "Haggis", "why": "Scotland's national dish brings earthy, peppery richness that stands up to the boldest single malts"},
        {"item": "Grilled Lamb", "why": "Rich, gamey lamb with herbs pairs naturally with hearty Highland malts and their heathery notes"},
        {"item": "Stilton Blue Cheese", "why": "Bold, pungent blue cheese stands up to malty complexity; the salt tames smoky heat"},
        {"item": "Isle of Mull Cheddar", "why": "This Scottish farmhouse cheddar has a tangy bite that complements Speyside honey-sweet malts beautifully"},
        {"item": "Dark Chocolate with Sea Salt", "why": "Salt amplifies the whisky's depth while dark cocoa mirrors maltiness and dried-fruit sherry notes"},
        {"item": "Sticky Toffee Pudding", "why": "Date-laden, caramel-drenched pudding matches sherry-cask Scotch note for note — a British classic"},
        {"item": "Cranachan", "why": "Scotland's traditional dessert of raspberries, oats, cream and honey was literally designed for Scotch"},
        {"item": "Smoked Oysters", "why": "Briny, smoky shellfish pair magnificently with Islay malts — sea meets peat in perfect harmony"},
        {"item": "Venison Steak", "why": "Lean, gamey venison with a peppery crust needs a robust Highland or Speyside malt beside it"},
        {"item": "Sushi (Fatty Tuna)", "why": "The buttery fat of otoro and a delicate Speyside share a silky richness — a sommelier favorite"},
        {"item": "Oatcakes with Honey", "why": "Simple Scottish oatcakes drizzled with heather honey bridge malt, grain, and sweetness effortlessly"},
    ],
    "irish": [
        {"item": "Soda Bread with Butter", "why": "Light, smooth Irish whiskey loves simple, honest flavors — the bread's tang and sweet butter are ideal"},
        {"item": "Oysters", "why": "Briny Galway oysters with a smooth, triple-distilled Irish whiskey is a celebrated coastal pairing"},
        {"item": "Irish Stew", "why": "Lamb, root vegetables, and herbs in a hearty stew complement the gentle warmth and grain sweetness"},
        {"item": "Cashel Blue", "why": "Ireland's famous blue cheese has a creamy, mild tang that mirrors the smoothness of pot-still whiskey"},
        {"item": "Aged Coolea", "why": "This Gouda-style Irish cheese has nutty, caramel depth that pairs beautifully with single pot still whiskey"},
        {"item": "Apple Tart", "why": "Fruity, approachable whiskey matches orchard-fruit desserts, especially with a cinnamon accent"},
        {"item": "Bailey's Cheesecake", "why": "Creamy, indulgent cheesecake with Irish cream echoes the whiskey's vanilla and dairy-smooth character"},
        {"item": "Smoked Mackerel", "why": "Oily, smoky fish with lemon is a classic pub pairing that lets the whiskey's green apple notes shine"},
        {"item": "Colcannon", "why": "Creamy mashed potatoes with cabbage and butter — comfort food that wraps around smooth Irish whiskey"},
        {"item": "Honey-Glazed Carrots", "why": "Roasted carrots' natural sweetness and honey glaze echo the honeyed, floral notes of pot still whiskey"},
        {"item": "Brown Bread Ice Cream", "why": "A uniquely Irish dessert — toasty breadcrumb and vanilla ice cream bridge grain and sweetness perfectly"},
    ],
    "japanese": [
        {"item": "Sashimi", "why": "Delicate raw fish lets the whisky's subtle complexity shine; the clean flavors never compete"},
        {"item": "Wagyu Beef", "why": "Rich umami and marbled fat meet refined, layered Japanese whisky — luxury paired with luxury"},
        {"item": "Yakitori (Tare-glazed)", "why": "Sweet soy glaze on grilled chicken skewers bridges the whisky's caramel and delicate smoke beautifully"},
        {"item": "Brie", "why": "Creamy, mild Brie complements Hibiki-style blended whisky's soft, floral, honeyed elegance"},
        {"item": "Smoked Mozzarella", "why": "Gentle smokiness and milky sweetness pair with the restrained, balanced profile of Japanese whisky"},
        {"item": "Mochi", "why": "Sweet rice cakes' soft, chewy texture echoes the rounded, silky mouthfeel of Japanese whisky"},
        {"item": "Matcha Chocolate", "why": "Earthy green tea bitterness and cacao create a complex bridge to Japanese whisky's Mizunara oak notes"},
        {"item": "Yuzu Tart", "why": "Bright citrus cuts through richness and mirrors the citrus peel notes common in Japanese blends"},
        {"item": "Dark Miso Soup", "why": "Deep, fermented umami creates a warming, harmonious pairing with malt-forward Japanese whisky"},
        {"item": "Tempura (Shrimp)", "why": "Light, crispy batter and sweet shrimp complement the whisky's delicacy without overwhelming it"},
        {"item": "Unagi (Grilled Eel)", "why": "Caramelized sweet soy glaze on rich eel is an izakaya classic alongside a Japanese highball"},
        {"item": "Pickled Ginger", "why": "Palate-cleansing sharpness between sips highlights the whisky's nuanced mid-palate flavors"},
    ],
    "rye": [
        {"item": "Pastrami on Rye", "why": "Spicy rye whiskey meets spiced, peppery cured meat on rye bread — a triple crown of rye flavor"},
        {"item": "Corned Beef Hash", "why": "Salty, peppery browned meat and potatoes match rye's bold, assertive spice and dry finish"},
        {"item": "Aged Gruyere", "why": "Nutty, savory Swiss cheese with crystalline crunch plays wonderfully against rye's peppery bite"},
        {"item": "Manchego", "why": "Firm, sheep's-milk cheese has a nutty tang that complements rye's herbal, grain-forward character"},
        {"item": "Charcuterie Board", "why": "Variety of cured meats, cornichons, mustard, and pickles are natural partners for rye's bold spice"},
        {"item": "Smoked Duck Breast", "why": "Rich, gamey duck with a peppery crust mirrors rye's signature spice and dry, lingering finish"},
        {"item": "Rye Bread with Caraway and Mustard", "why": "Caraway seeds and sharp mustard echo the herbal, spicy grain character of the whiskey itself"},
        {"item": "Gingerbread", "why": "Warm ginger, cinnamon, and clove in gingerbread mirror rye's baking spice notes almost exactly"},
        {"item": "Dark Chocolate with Chili", "why": "Spicy chocolate amplifies rye's peppery heat while cocoa bitterness adds depth — bold meets bold"},
        {"item": "Pear Tart with Cardamom", "why": "Pear's gentle sweetness and cardamom's warm spice create an elegant counterpoint to rye's bite"},
        {"item": "Kimchi", "why": "Fermented heat and funky complexity create an exciting contrast with rye's dry spice — adventurous and addictive"},
        {"item": "Reuben Sandwich", "why": "Sauerkraut, Swiss cheese, and corned beef combine every flavor that makes rye whiskey sing"},
    ],
    "canadian": [
        {"item": "Maple Glazed Salmon", "why": "Light, smooth Canadian whisky loves maple sweetness — a pairing that's quintessentially Canadian"},
        {"item": "Poutine", "why": "Rich gravy, melted cheese curds, and crispy fries pair with the easy-drinking, versatile whisky"},
        {"item": "Tourtiere", "why": "Quebec's traditional meat pie with warm spices complements Canadian whisky's gentle, approachable spice"},
        {"item": "Smoked Gouda", "why": "Mild smokiness and creamy texture complement the smooth, mellow profile of Canadian blends"},
        {"item": "Oka Cheese", "why": "This famous Quebec washed-rind cheese has a nutty, fruity character that matches light Canadian whisky"},
        {"item": "Apple Crumble", "why": "Baked apple, cinnamon, and buttery oat topping match Canadian whisky's gentle fruit and grain notes"},
        {"item": "Butter Tarts", "why": "Canada's iconic pastry — gooey caramel filling mirrors the butterscotch notes in smooth Canadian whisky"},
        {"item": "Nanaimo Bars", "why": "Layered chocolate, custard, and coconut offer a sweet richness that balances the whisky's lightness"},
        {"item": "Peameal Bacon", "why": "Lean, cornmeal-crusted bacon has a sweet-savory quality that pairs naturally with Canadian whisky's soft grain character"},
        {"item": "Cedar-Planked Whitefish", "why": "Delicate, smoky fish from the Great Lakes tradition matches the whisky's subtle woodiness"},
        {"item": "Wild Blueberry Compote on Brie", "why": "Tart wild blueberries and creamy Brie bridge Canadian whisky's fruit and vanilla notes elegantly"},
        {"item": "Montreal Smoked Meat", "why": "Peppery, smoky brisket is bolder than the whisky but the contrast creates an exciting, balanced bite"},
    ],
    "wheat": [
        {"item": "Honeycomb", "why": "Pure honeycomb's floral sweetness directly mirrors wheat whiskey's signature honey and soft grain notes"},
        {"item": "Brioche French Toast", "why": "Buttery, egg-rich brioche with maple syrup echoes the pillowy sweetness and vanilla of wheat whiskey"},
        {"item": "Triple-Cream Brie", "why": "Ultra-creamy, mild cheese matches wheat whiskey's famously soft, silky mouthfeel and gentle flavor"},
        {"item": "Fresh Burrata", "why": "Milky, delicate burrata with a drizzle of honey bridges the whiskey's cream and floral character"},
        {"item": "Creme Brulee", "why": "Caramelized sugar crust over vanilla custard mirrors wheat whiskey's toasted sweetness and smooth body"},
        {"item": "Lemon Panna Cotta", "why": "Light citrus and silky cream complement wheat whiskey's brightness and gentle, rounded finish"},
        {"item": "Shortbread Cookies", "why": "Buttery, crumbly shortbread echoes the wheat whiskey's soft grain sweetness and biscuit-like quality"},
        {"item": "Prosciutto and Melon", "why": "Sweet melon and salty ham create a delicate balance that matches wheat whiskey's approachable softness"},
        {"item": "Lobster with Drawn Butter", "why": "Sweet, tender lobster dipped in butter mirrors the whiskey's rich, creamy, gently sweet profile"},
        {"item": "Roasted Chicken with Herbs", "why": "Simply roasted chicken with thyme and lemon is a gentle pairing that won't overpower the subtle grain"},
        {"item": "White Peach with Ricotta", "why": "Ripe peach and fresh ricotta match the whiskey's stone fruit notes and creamy texture beautifully"},
        {"item": "Lavender Honey Scones", "why": "Floral lavender and honey amplify the delicate, perfumed qualities that make wheat whiskey unique"},
    ],
    "single malt": [
        {"item": "Smoked Salmon", "why": "Oily, smoky fish is a natural partner for malt-driven whisky — the fat carries barrel flavors beautifully"},
        {"item": "Roasted Nuts (Walnut & Almond)", "why": "Toasted nuts echo the malty, barrel-aged nuttiness that defines the single malt category"},
        {"item": "Aged Comte", "why": "Complex, nutty Comte has crystalline crunch and caramel depth that mirrors aged single malt beautifully"},
        {"item": "Roquefort", "why": "Bold blue cheese with honeycomb is a classic whisky pairing — the salt and funk need malt's backbone"},
        {"item": "Dark Chocolate Truffles", "why": "Rich ganache with cocoa bitterness complements the malt's dried fruit, oak tannin, and vanilla"},
        {"item": "Sticky Toffee Pudding", "why": "Date-laden, caramel-drenched pudding is tailor-made for sherry-cask single malts with dried fruit notes"},
        {"item": "Oat Flapjack with Honey", "why": "Chewy oat bars drizzled with honey bridge the grain, sweetness, and malty backbone of the whisky"},
        {"item": "Venison Steak", "why": "Lean, gamey venison with juniper and black pepper demands a robust single malt to stand beside it"},
        {"item": "Pan-Seared Duck with Cherry Reduction", "why": "Rich duck fat and tart cherry sauce mirror sherry-cask malts' fruit and savory depth"},
        {"item": "Beef Carpaccio", "why": "Paper-thin raw beef with olive oil and Parmesan lets a refined single malt's complexity take center stage"},
        {"item": "Sushi (Fatty Tuna)", "why": "Otoro's buttery richness pairs surprisingly well with elegant Speyside or Japanese single malts"},
        {"item": "Fig and Walnut Bread", "why": "Dried figs and toasted walnuts echo the dried fruit and nut notes of well-aged single malts perfectly"},
    ],
}

_FOOD_DEFAULT = [
    {"item": "Dark Chocolate (70%+ cacao)", "why": "Cocoa bitterness and vanilla universally complement oak-aged whiskey's caramel and tannin"},
    {"item": "Aged Cheese Board", "why": "Sharp, complex aged cheeses (cheddar, Gouda, Parmesan) match whiskey's depth across all styles"},
    {"item": "Roasted Nuts (Almonds & Pecans)", "why": "Toasty, nutty flavors echo oak barrel notes — the simplest and most reliable whiskey companion"},
    {"item": "Charcuterie with Grainy Mustard", "why": "Cured meats provide savory contrast while mustard bridges the whiskey's spice and tang"},
    {"item": "Dried Fruit (Apricots & Figs)", "why": "Concentrated sweetness and chewiness mirror the dried fruit notes found in most barrel-aged whiskeys"},
]

_COCKTAILS_BY_CATEGORY = {
    # ── BOURBON (10 cocktails) ───────────────────────────────────────────
    "bourbon": [
        {"name": "Old Fashioned", "ingredients": "2oz bourbon, 1 sugar cube, 2 dashes Angostura bitters, orange peel", "desc": "The quintessential bourbon cocktail — simple, timeless, and the benchmark by which all whiskey drinks are measured."},
        {"name": "Mint Julep", "ingredients": "2.5oz bourbon, 8-10 fresh mint leaves, 0.5oz simple syrup, crushed ice", "desc": "The official drink of the Kentucky Derby — cool, aromatic, and dangerously refreshing on a warm afternoon."},
        {"name": "Whiskey Sour", "ingredients": "2oz bourbon, 1oz fresh lemon juice, 0.75oz simple syrup, 0.5oz egg white (optional)", "desc": "Tart, sweet, and velvety when shaken with egg white — the perfect balance of bright citrus and rich bourbon."},
        {"name": "Kentucky Mule", "ingredients": "2oz bourbon, 0.5oz fresh lime juice, 4oz ginger beer, lime wheel", "desc": "Bourbon's spicy twist on the Moscow Mule — the ginger heat amplifies the whiskey's caramel warmth."},
        {"name": "Brown Derby", "ingredients": "2oz bourbon, 1oz fresh grapefruit juice, 0.5oz honey syrup", "desc": "A Hollywood classic from the Vendome Club — bittersweet grapefruit meets floral honey and rich bourbon."},
        {"name": "Paper Plane", "ingredients": "0.75oz bourbon, 0.75oz Aperol, 0.75oz Amaro Nonino, 0.75oz fresh lemon juice", "desc": "Sam Ross's modern masterpiece — bittersweet, citrusy, and perfectly balanced with equal-parts elegance."},
        {"name": "Gold Rush", "ingredients": "2oz bourbon, 0.75oz fresh lemon juice, 0.75oz honey syrup", "desc": "A honey-kissed Whiskey Sour from Milk & Honey — silky, bright, and irresistibly drinkable."},
        {"name": "Bourbon Smash", "ingredients": "2oz bourbon, 0.75oz simple syrup, 4 lemon wedges, 6 fresh mint leaves", "desc": "A muddled celebration of summer — herbaceous mint and bright lemon tame bourbon's oak-aged heat."},
        {"name": "Hot Toddy", "ingredients": "2oz bourbon, 1 tbsp honey, 0.75oz fresh lemon juice, 4oz hot water, cinnamon stick", "desc": "The ultimate cold-weather remedy — warm honey, lemon, and bourbon wrap around you like a blanket."},
        {"name": "New York Sour", "ingredients": "2oz bourbon, 1oz fresh lemon juice, 0.75oz simple syrup, 0.5oz dry red wine float", "desc": "A Whiskey Sour crowned with a dramatic red wine float — visually stunning and layered with dark fruit complexity."},
    ],
    # ── SCOTCH (8 cocktails) ─────────────────────────────────────────────
    "scotch": [
        {"name": "Rob Roy", "ingredients": "2oz blended scotch, 1oz sweet vermouth, 2 dashes Angostura bitters, cherry garnish", "desc": "Scotland's answer to the Manhattan — smoky, sophisticated, and named for a legendary Highland outlaw."},
        {"name": "Penicillin", "ingredients": "2oz blended scotch, 0.75oz fresh lemon juice, 0.75oz honey-ginger syrup, 0.25oz Islay single malt float", "desc": "Sam Ross's modern classic from Milk & Honey — the smoky Islay float over honeyed ginger is pure cocktail genius."},
        {"name": "Blood & Sand", "ingredients": "0.75oz scotch, 0.75oz sweet vermouth, 0.75oz Cherry Heering, 0.75oz fresh orange juice", "desc": "A Prohibition-era equal-parts marvel named for the Valentino film — fruity, complex, and surprisingly bright."},
        {"name": "Rusty Nail", "ingredients": "2oz scotch, 0.75oz Drambuie, lemon twist", "desc": "Honeyed herbal Drambuie melds with scotch in this Rat Pack-era classic — malty sweetness with a velvet finish."},
        {"name": "Bobby Burns", "ingredients": "2oz scotch, 1oz sweet vermouth, 0.25oz Benedictine, lemon twist", "desc": "Named for Scotland's beloved poet — herbal, warm, and perfect for a contemplative evening by the fire."},
        {"name": "Scotch Highball", "ingredients": "2oz scotch, 4oz chilled soda water, lemon twist", "desc": "Crisp, clean, and effervescent — a lighter way to enjoy scotch that opens up its delicate floral and malty notes."},
        {"name": "Godfather", "ingredients": "2oz scotch, 0.75oz Amaretto, orange peel", "desc": "Almond sweetness tames scotch's intensity in this smooth, after-dinner sipper inspired by the Corleones."},
        {"name": "Morning Glory Fizz", "ingredients": "2oz scotch, 0.75oz fresh lemon juice, 0.5oz simple syrup, 0.5oz egg white, 2 dashes absinthe, soda water", "desc": "A Victorian brunch cocktail — frothy, herbaceous, and effervescent with a whisper of anise from the absinthe."},
    ],
    # ── IRISH (8 cocktails) ──────────────────────────────────────────────
    "irish": [
        {"name": "Irish Coffee", "ingredients": "1.5oz Irish whiskey, 6oz hot brewed coffee, 1 tbsp brown sugar, lightly whipped cream float", "desc": "Born at Shannon Airport on a cold night — warm, bittersweet, and crowned with a cloud of cream."},
        {"name": "Tipperary", "ingredients": "1.5oz Irish whiskey, 1oz sweet vermouth, 0.5oz green Chartreuse, 2 dashes Angostura bitters", "desc": "Herbal and elegant — a forgotten pre-Prohibition classic that showcases Irish whiskey's smooth versatility."},
        {"name": "Irish Maid", "ingredients": "2oz Irish whiskey, 0.75oz elderflower liqueur, 0.75oz fresh lemon juice, 2 slices cucumber", "desc": "Dale DeGroff's garden-fresh creation — cucumber and elderflower make this impossibly crisp and refined."},
        {"name": "Emerald", "ingredients": "2oz Irish whiskey, 1oz sweet vermouth, 2 dashes orange bitters, orange twist", "desc": "A gentle Irish twist on the Manhattan — lighter, smoother, and glowing with citrus warmth."},
        {"name": "Irish Buck", "ingredients": "2oz Irish whiskey, 0.5oz fresh lemon juice, 4oz ginger ale, lemon wedge", "desc": "Effervescent and easygoing — ginger ale's spice brings out the honey notes in smooth Irish whiskey."},
        {"name": "Blackthorn", "ingredients": "1.5oz Irish whiskey, 1.5oz dry vermouth, 3 dashes Pernod, 3 dashes Angostura bitters", "desc": "A forgotten Irish aperitif with an anise whisper — dry, aromatic, and hauntingly herbaceous."},
        {"name": "Celtic Smash", "ingredients": "2oz Irish whiskey, 0.75oz honey syrup, 6 fresh mint leaves, 3 lemon wedges", "desc": "Ireland meets the Julep — muddled mint and honey transform silky whiskey into a bright, garden-fresh sipper."},
        {"name": "Paddy Cocktail", "ingredients": "1.5oz Irish whiskey, 1oz sweet vermouth, 2 dashes Angostura bitters", "desc": "Named for Paddy Flaherty's beloved whiskey brand — simple, approachable, and a gentle introduction to stirred drinks."},
    ],
    # ── JAPANESE (8 cocktails) ───────────────────────────────────────────
    "japanese": [
        {"name": "Japanese Highball", "ingredients": "2oz Japanese whisky, 4oz very cold soda water, large clear ice", "desc": "Elevated to ritual in Tokyo's bars — precise, crystalline, and the most respectful way to honor Japanese whisky."},
        {"name": "Mizuwari", "ingredients": "1.5oz Japanese whisky, 2.5oz cold mineral water, large hand-cut ice", "desc": "Gently diluted through 13 meditative stirs — unlocks subtle floral and fruit notes invisible in a neat pour."},
        {"name": "Whisky Sour Tokyo Style", "ingredients": "2oz Japanese whisky, 0.75oz fresh lemon juice, 0.5oz simple syrup, 0.5oz egg white, cherry blossom garnish", "desc": "Silky and precise — the Japanese approach brings a lighter, more balanced elegance to the classic sour."},
        {"name": "Oyuwari", "ingredients": "1.5oz Japanese whisky, 2.5oz hot water (175F/80C)", "desc": "The winter mizuwari — warm water coaxes out deep umami and toasted grain notes on cold evenings."},
        {"name": "Japanese Cocktail", "ingredients": "2oz Japanese whisky, 0.5oz orgeat, 2 dashes Angostura bitters, lemon twist", "desc": "An adaptation of the 1862 Jerry Thomas original — almond-sweet orgeat marries beautifully with refined Japanese malt."},
        {"name": "Bamboo", "ingredients": "1.5oz Japanese whisky, 1.5oz dry vermouth, 1 dash Angostura bitters, 1 dash orange bitters", "desc": "Inspired by the classic Yokohama Grand Hotel cocktail — dry, elegant, and perfect before dinner."},
        {"name": "Sakura Spritz", "ingredients": "1.5oz Japanese whisky, 0.5oz cherry blossom liqueur, 0.5oz fresh lemon juice, 3oz sparkling water, cherry blossom garnish", "desc": "A blush-pink celebration of spring — floral, delicate, and as beautiful to look at as it is to drink."},
        {"name": "Umami Old Fashioned", "ingredients": "2oz Japanese whisky, 0.25oz mirin, 2 dashes Angostura bitters, shiso leaf garnish", "desc": "A Tokyo cocktail bar innovation — mirin adds a savory sweetness that deepens the whisky's complexity."},
    ],
    # ── RYE (8 cocktails) ────────────────────────────────────────────────
    "rye": [
        {"name": "Manhattan", "ingredients": "2oz rye, 1oz sweet vermouth, 2 dashes Angostura bitters, Luxardo cherry", "desc": "The king of cocktails — rye's peppery spice and dry backbone are essential to the Manhattan's soul."},
        {"name": "Sazerac", "ingredients": "2oz rye, 1 sugar cube, 4 dashes Peychaud's bitters, absinthe rinse, lemon peel expressed and discarded", "desc": "New Orleans in a glass — America's oldest cocktail is bold, aromatic, and layered with anise and spice."},
        {"name": "Boulevardier", "ingredients": "1.5oz rye, 1oz sweet vermouth, 1oz Campari, orange twist", "desc": "A Negroni's whiskey-drinking cousin — bitter Campari and sweet vermouth dance with rye's peppery kick."},
        {"name": "Vieux Carre", "ingredients": "1oz rye, 1oz cognac, 1oz sweet vermouth, 0.25oz Benedictine, 2 dashes Peychaud's bitters, 2 dashes Angostura bitters", "desc": "The French Quarter's most complex cocktail — rich, herbal, and layered like the history of New Orleans itself."},
        {"name": "Toronto", "ingredients": "2oz rye, 0.25oz Fernet-Branca, 0.25oz simple syrup, 2 dashes Angostura bitters, orange twist", "desc": "Fernet's bitter menthol edge sharpens rye's spice into a bracing, digestif-style cocktail that rewards the bold."},
        {"name": "De La Louisiane", "ingredients": "1.5oz rye, 0.75oz sweet vermouth, 0.75oz Benedictine, 3 dashes absinthe, 3 dashes Peychaud's bitters", "desc": "A lavish Crescent City sipper — herbal Benedictine and absinthe give this cocktail an almost mystical depth."},
        {"name": "Algonquin", "ingredients": "2oz rye, 1oz dry vermouth, 1oz fresh pineapple juice", "desc": "Named for the legendary literary hotel — tropical pineapple is an unexpected but brilliant partner for spicy rye."},
        {"name": "Rye Witch", "ingredients": "2oz rye, 0.75oz Strega, 0.25oz maraschino liqueur, 2 dashes orange bitters", "desc": "A modern craft bar gem — herbal Strega and floral maraschino conjure something dark and enchanting."},
    ],
    # ── CANADIAN (8 cocktails) ───────────────────────────────────────────
    "canadian": [
        {"name": "Canadian Cocktail", "ingredients": "2oz Canadian whisky, 0.5oz Cointreau, 1 dash Angostura bitters, 1 tsp simple syrup", "desc": "Smooth and orange-accented — a classic that lets Canadian whisky's gentle, easy-drinking character shine."},
        {"name": "Whisky Ginger", "ingredients": "2oz Canadian whisky, 4oz ginger ale, lime wedge", "desc": "Canada's unofficial national drink — light, fizzy, and universally beloved at every backyard gathering."},
        {"name": "Canadian Old Fashioned", "ingredients": "2oz Canadian whisky, 0.25oz maple syrup, 2 dashes Angostura bitters, orange peel", "desc": "Maple syrup instead of sugar — the most Canadian spin on the world's most iconic cocktail."},
        {"name": "Caribou", "ingredients": "3oz Canadian whisky, 3oz red wine (port-style), 1oz maple syrup", "desc": "A Quebecois winter warmer served at Carnaval — fortifying, sweet, and designed to beat sub-zero temperatures."},
        {"name": "Canadian Sour", "ingredients": "2oz Canadian whisky, 1oz fresh lemon juice, 0.75oz maple syrup, 0.5oz egg white", "desc": "Maple-sweetened and velvet-smooth — Canada's answer to the Whiskey Sour is gentler and more nuanced."},
        {"name": "Norseman", "ingredients": "2oz Canadian whisky, 0.5oz sweet vermouth, 0.5oz dry vermouth, 1 dash Angostura bitters, lemon twist", "desc": "A perfectly balanced perfect Manhattan variation — the split vermouth lets Canadian whisky's light body sing."},
        {"name": "Calgary Red Eye", "ingredients": "2oz Canadian whisky, 4oz tomato juice, light beer float, hot sauce, Worcestershire", "desc": "The Prairie morning-after cure — part Caesar, part pick-me-up, and entirely Canadian."},
        {"name": "Nor'Easter", "ingredients": "2oz Canadian whisky, 0.5oz fresh lime juice, 0.5oz maple syrup, 4oz ginger beer", "desc": "A maple-ginger mule built for cold Atlantic nights — warming, spicy, and deceptively easy to drink."},
    ],
    # ── WHEAT (8 cocktails) ──────────────────────────────────────────────
    "wheat": [
        {"name": "Wheat Old Fashioned", "ingredients": "2oz wheat whiskey, 0.25oz honey syrup, 2 dashes orange bitters, orange peel", "desc": "Honey syrup and orange bitters highlight wheat whiskey's naturally soft, bread-like sweetness."},
        {"name": "Honeyed Sour", "ingredients": "2oz wheat whiskey, 0.75oz fresh lemon juice, 0.75oz lavender-honey syrup, 0.5oz egg white", "desc": "Floral, silky, and gentle — lavender and honey amplify wheat whiskey's pillowy softness."},
        {"name": "Wheat Smash", "ingredients": "2oz wheat whiskey, 0.75oz simple syrup, 4 lemon wedges, 6 fresh basil leaves", "desc": "Basil instead of mint transforms the smash — herbaceous and aromatic with wheat's smooth caramel finish."},
        {"name": "Amber Harvest", "ingredients": "2oz wheat whiskey, 1oz fresh apple cider, 0.5oz cinnamon syrup, 2 dashes Angostura bitters", "desc": "An autumn sipper — warm cinnamon and crisp apple bring out wheat whiskey's baked-bread and vanilla notes."},
        {"name": "Gentle Manhattan", "ingredients": "2oz wheat whiskey, 1oz sweet vermouth, 1 dash Angostura bitters, 1 dash orange bitters, cherry", "desc": "Wheat's delicate sweetness creates a softer, more approachable Manhattan — velvety and easy to love."},
        {"name": "Golden Mile", "ingredients": "2oz wheat whiskey, 0.75oz Aperol, 0.5oz fresh lemon juice, 0.5oz honey syrup, sprig of thyme", "desc": "Aperol's gentle bitterness and thyme's earthiness frame wheat whiskey's soft vanilla and caramel notes."},
        {"name": "Bread Basket", "ingredients": "2oz wheat whiskey, 0.5oz Frangelico, 0.5oz cream, grated nutmeg", "desc": "A dessert in a glass — hazelnut liqueur and cream echo the toasty, bready character of wheat whiskey."},
        {"name": "Prairie Fizz", "ingredients": "2oz wheat whiskey, 0.75oz fresh lemon juice, 0.5oz simple syrup, 2oz sparkling wine", "desc": "Sparkling wine adds celebratory effervescence to wheat whiskey's mellow warmth — light, bright, and festive."},
    ],
    # ── SINGLE MALT (8 cocktails) ────────────────────────────────────────
    "single malt": [
        {"name": "Penicillin", "ingredients": "2oz single malt scotch, 0.75oz fresh lemon juice, 0.75oz honey-ginger syrup, 0.25oz peated single malt float", "desc": "The definitive modern scotch cocktail — the peated float over honeyed ginger is a masterclass in layered flavors."},
        {"name": "Rob Roy", "ingredients": "2oz single malt scotch, 1oz sweet vermouth, 2 dashes Angostura bitters, cherry", "desc": "Using single malt instead of blended adds depth and character — each distillery creates a different Rob Roy."},
        {"name": "Single Malt Highball", "ingredients": "2oz single malt scotch, 4oz chilled soda water, large clear ice, lemon twist", "desc": "A Speyside or Highland malt opens up beautifully with bubbles — floral, honeyed, and effortlessly elegant."},
        {"name": "Smoky Cokey", "ingredients": "2oz peated single malt, 4oz Mexican Coca-Cola, large ice, lime wedge", "desc": "A guilty pleasure turned cult classic — the Islay-meets-cola combination is unexpectedly complex and addictive."},
        {"name": "Scotch Sour", "ingredients": "2oz single malt scotch, 0.75oz fresh lemon juice, 0.75oz honey syrup, 0.5oz egg white", "desc": "Honey and single malt are natural partners — the egg white adds a luxurious texture to this malty, citrus delight."},
        {"name": "Affinity", "ingredients": "1oz single malt scotch, 1oz dry vermouth, 1oz sweet vermouth, 2 dashes Angostura bitters", "desc": "A split-vermouth cocktail from the early 1900s — dry, complex, and a masterclass in aromatic balance."},
        {"name": "Bobby Burns", "ingredients": "2oz single malt scotch, 1oz sweet vermouth, 0.25oz Benedictine, lemon twist", "desc": "Named for Scotland's national poet — herbal Benedictine brings warmth to the single malt's complexity."},
        {"name": "Laphroaig Project", "ingredients": "1.5oz peated single malt, 0.75oz yellow Chartreuse, 0.75oz fresh lime juice, 0.5oz maraschino liqueur", "desc": "A Last Word variation for peat lovers — herbal, smoky, and electrifyingly complex."},
    ],
}

_COCKTAILS_DEFAULT = [
    {"name": "Old Fashioned", "ingredients": "2oz whiskey, 1 sugar cube, 2 dashes Angostura bitters, orange peel", "desc": "Works with almost any whiskey — the timeless original that lets the spirit speak for itself."},
    {"name": "Whiskey Sour", "ingredients": "2oz whiskey, 1oz fresh lemon juice, 0.75oz simple syrup, 0.5oz egg white (optional)", "desc": "Bright, balanced, and universally flattering — a perfect starting point for any bottle."},
    {"name": "Highball", "ingredients": "2oz whiskey, 4oz chilled soda water, large ice", "desc": "Simple and effervescent — lets the whiskey's character come through with refreshing clarity."},
    {"name": "Whiskey Ginger", "ingredients": "2oz whiskey, 4oz ginger ale, lime wedge", "desc": "The ultimate crowd-pleaser — ginger's warmth complements every style of whiskey."},
    {"name": "Hot Toddy", "ingredients": "2oz whiskey, 1 tbsp honey, 0.75oz fresh lemon juice, 4oz hot water, cinnamon stick", "desc": "The cold-weather classic that turns any whiskey into liquid comfort on a chilly evening."},
]

# ── Flavor-triggered bonus food pairings ────────────────────────────────

_FLAVOR_BONUS_PAIRINGS = {
    "smoky": [
        {"item": "Grilled Steak", "why": "Char and smoke on meat mirrors the whiskey's campfire character — the most natural smoky pairing"},
        {"item": "Smoked Almonds", "why": "Concentrated smoke and nutty crunch amplify peaty whisky's toasty, roasted qualities"},
        {"item": "Bacon-Wrapped Dates", "why": "Sweet dates inside smoky bacon create a bite-sized flavor bomb that matches smoky whiskey perfectly"},
    ],
    "peaty": [
        {"item": "Smoked Oysters", "why": "Briny, smoky shellfish are an Islay classic — maritime peat and ocean minerals in perfect harmony"},
        {"item": "Dark Chocolate with Smoked Salt", "why": "Smoky salt and bitter cocoa intensify peat's earthy, medicinal complexity into something sublime"},
        {"item": "Grilled Steak", "why": "Char and smoke on meat mirrors the whiskey's campfire character — the most natural peaty pairing"},
    ],
    "honey": [
        {"item": "Baklava", "why": "Layered honey and nut pastry amplifies the whiskey's natural sweetness with matching floral notes"},
        {"item": "Honeycomb with Aged Cheese", "why": "Raw honeycomb drizzled over sharp cheese creates the ideal sweet-savory bridge for honey-forward whiskey"},
        {"item": "Glazed Ham", "why": "Honey-glazed ham's sweetness and salty cure echo and enhance the whiskey's golden, honeyed warmth"},
    ],
    "sweet": [
        {"item": "Caramel Flan", "why": "Silky custard with burnt caramel sauce mirrors sweet whiskey's vanilla and toffee in liquid dessert form"},
        {"item": "Candied Pecans", "why": "Sugar-coated nuts bridge sweet whiskey's caramel with toasty barrel notes in every crunchy bite"},
        {"item": "Baklava", "why": "Layered honey and nut pastry amplifies the whiskey's natural sweetness with matching floral notes"},
    ],
    "fruity": [
        {"item": "Fresh Fruit & Cream", "why": "Fresh berries or stone fruit echo the whiskey's bright, fruity esters with a clean dairy finish"},
        {"item": "Baked Brie with Fig Jam", "why": "Warm, gooey cheese with sweet fig preserves amplifies fruity whiskey's jammy, lush character"},
        {"item": "Duck a l'Orange", "why": "Rich duck with orange sauce creates a savory-fruity bridge that matches fruit-forward whiskey beautifully"},
    ],
    "citrus": [
        {"item": "Ceviche", "why": "Lime-cured fish with chili and cilantro mirrors citrusy whiskey's brightness and creates an exciting pairing"},
        {"item": "Lemon Tart", "why": "Tangy lemon curd in buttery pastry directly amplifies the whiskey's citrus peel and vanilla notes"},
        {"item": "Fresh Fruit & Cream", "why": "Citrus segments and berries with whipped cream echo the whiskey's bright, zesty character"},
    ],
    "spicy": [
        {"item": "Szechuan Peppercorn Dishes", "why": "Numbing spice and aromatic heat create an exciting, tingling pairing that amplifies spicy whiskey"},
        {"item": "Jerk Chicken", "why": "Caribbean spice blend with scotch bonnet heat stands up to and enhances the whiskey's peppery kick"},
        {"item": "Spiced Dark Chocolate", "why": "Chili-infused chocolate turns up the heat while cocoa provides a bitter-sweet anchor for spicy whiskey"},
    ],
    "vanilla": [
        {"item": "Vanilla Bean Panna Cotta", "why": "Pure vanilla custard creates a resonant echo with the whiskey's barrel-derived vanilla lactones"},
        {"item": "Creme Brulee", "why": "Caramelized sugar crust over vanilla custard mirrors the whiskey's toasted oak and vanilla character"},
        {"item": "Buttered Popcorn", "why": "Butter and salt on popcorn unlock vanilla whiskey's sweetness — surprisingly simple and irresistible"},
    ],
    "caramel": [
        {"item": "Salted Caramel Brownies", "why": "Salt cuts through sweetness while caramel and chocolate build on the whiskey's toffee barrel notes"},
        {"item": "Toffee Apples", "why": "Hard caramel shell over tart apple creates a sweet-sour contrast that caramel whiskey craves"},
        {"item": "Creme Brulee", "why": "Torched sugar crust is literally caramelization — it mirrors the whiskey's Maillard reaction flavors exactly"},
    ],
    "floral": [
        {"item": "Lavender Shortbread", "why": "Floral lavender in buttery cookies resonates with the whiskey's perfumed, delicate aromatics"},
        {"item": "Goat Cheese with Honey", "why": "Tangy, creamy chevre with floral honey creates an elegant pairing for aromatic, floral whiskey"},
        {"item": "Rose-Scented Turkish Delight", "why": "Fragrant rosewater and powdered sugar complement floral whiskey's perfumed, ethereal quality"},
    ],
    "nutty": [
        {"item": "Roasted Hazelnuts", "why": "Toasted hazelnuts directly amplify the whiskey's nutty barrel character — like-with-like perfection"},
        {"item": "Almond Biscotti", "why": "Crunchy, twice-baked almond cookies bridge nutty whiskey's toasty grain and oak-barrel sweetness"},
        {"item": "Nutella on Toast", "why": "Hazelnut-chocolate spread on warm bread is an indulgent, accessible match for nutty whiskey"},
    ],
    "creamy": [
        {"item": "Triple-Cream Brie", "why": "Ultra-rich, buttery cheese matches creamy whiskey's luxurious, smooth mouthfeel texture-for-texture"},
        {"item": "Lobster Bisque", "why": "Velvety, rich soup with sweet shellfish mirrors creamy whiskey's silky body and gentle sweetness"},
        {"item": "Tiramisu", "why": "Layers of mascarpone, coffee, and cocoa create a creamy, complex dessert that matches the whiskey's texture"},
    ],
}


def _normalize_category(raw: str) -> str:
    """Normalize a whiskey category to match our pairing dictionary keys.

    Handles variations like 'Bourbon', 'SCOTCH', 'Single Malt Scotch',
    'Irish Whiskey', 'Japanese Whisky', etc.
    """
    cat = (raw or "").lower().strip()
    # Direct match first
    if cat in _FOOD_BY_CATEGORY:
        return cat
    # Check if any known category key appears in the raw string
    for key in _FOOD_BY_CATEGORY:
        if key in cat:
            return key
    # Common aliases
    aliases = {
        "whisky": "scotch",
        "malt": "single malt",
        "tennessee": "bourbon",
        "corn": "bourbon",
        "blend": "scotch",
    }
    for alias, mapped in aliases.items():
        if alias in cat:
            return mapped
    return cat


@router.get("/{whiskey_id}")
def get_pairings(whiskey_id: int, db: Session = Depends(get_db)):
    """Return food pairings and cocktail suggestions for a whiskey."""
    whiskey = db.query(models.Whiskey).filter(models.Whiskey.id == whiskey_id).first()
    if not whiskey:
        raise HTTPException(status_code=404, detail="Whiskey not found")

    cat = _normalize_category(whiskey.category)

    food = _FOOD_BY_CATEGORY.get(cat, _FOOD_DEFAULT)
    cocktails = _COCKTAILS_BY_CATEGORY.get(cat, _COCKTAILS_DEFAULT)

    # Add flavor-specific bonus pairings if we have flavor data
    profile = (whiskey.flavor_profile or "").lower()
    bonus = []
    for flavor_key, flavor_pairings in _FLAVOR_BONUS_PAIRINGS.items():
        if flavor_key in profile:
            bonus.extend(flavor_pairings)

    # Deduplicate by item name, keep first occurrence
    seen = set()
    unique_bonus = []
    food_items = {f["item"] for f in food}
    for b in bonus:
        if b["item"] not in seen and b["item"] not in food_items:
            seen.add(b["item"])
            unique_bonus.append(b)

    return {
        "whiskey_id": whiskey.id,
        "whiskey_name": whiskey.name,
        "category": whiskey.category,
        "food_pairings": _with_images(food + unique_bonus[:3]),  # max 3 bonus
        "cocktails": _cocktails_with_images(cocktails),
    }
