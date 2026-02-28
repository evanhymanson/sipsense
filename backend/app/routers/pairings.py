"""
Food pairings & cocktail suggestions for whiskeys.

Uses a rule-based mapping for instant results, with optional AI enhancement.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import models
from ..database import get_db

router = APIRouter(prefix="/pairings", tags=["pairings"])

# ── Static pairing rules by category / flavor ───────────────────────────

_FOOD_BY_CATEGORY = {
    "bourbon": [
        {"item": "Smoked BBQ Brisket", "why": "The char and sweetness of bourbon complement smoky meat perfectly"},
        {"item": "Dark Chocolate", "why": "Cocoa and vanilla notes mirror bourbon's caramel-oak character"},
        {"item": "Pecan Pie", "why": "Nutty sweetness echoes bourbon's corn-forward richness"},
        {"item": "Aged Cheddar", "why": "Sharp, crumbly cheese contrasts bourbon's sweetness beautifully"},
    ],
    "scotch": [
        {"item": "Smoked Salmon", "why": "Smoke meets smoke — a classic Scottish pairing"},
        {"item": "Blue Cheese", "why": "Bold, pungent cheese stands up to malty complexity"},
        {"item": "Dark Chocolate with Sea Salt", "why": "Salt amplifies the whisky's depth and maltiness"},
        {"item": "Grilled Lamb", "why": "Rich, gamey meat pairs with hearty Highland malts"},
    ],
    "irish": [
        {"item": "Soda Bread with Butter", "why": "Light, smooth Irish whiskey loves simple, honest flavors"},
        {"item": "Oysters", "why": "Briny oysters pair beautifully with light, floral Irish whiskey"},
        {"item": "Apple Tart", "why": "Fruity, approachable whiskey matches fruit-forward desserts"},
        {"item": "Mild Gouda", "why": "Creamy, gentle cheese complements the smooth finish"},
    ],
    "japanese": [
        {"item": "Sashimi", "why": "Delicate fish lets the whisky's subtle complexity shine"},
        {"item": "Wagyu Beef", "why": "Rich umami meets refined, layered Japanese whisky"},
        {"item": "Mochi", "why": "Sweet rice cakes echo the soft, rounded texture"},
        {"item": "Dark Miso Soup", "why": "Deep umami flavors create a harmonious pairing"},
    ],
    "rye": [
        {"item": "Pastrami on Rye", "why": "Spicy whiskey meets spiced, cured meat — natural partners"},
        {"item": "Gingerbread", "why": "Rye's spice notes mirror warm ginger and cinnamon"},
        {"item": "Aged Gruyère", "why": "Nutty, savory cheese plays well with rye's peppery bite"},
        {"item": "Charcuterie Board", "why": "Variety of cured meats and pickles love rye's spice"},
    ],
    "canadian": [
        {"item": "Maple Glazed Salmon", "why": "Light, smooth Canadian whisky loves maple sweetness"},
        {"item": "Poutine", "why": "Rich, savory comfort food pairs with easy-drinking whisky"},
        {"item": "Apple Crumble", "why": "Fruit and spice match Canadian whisky's gentle character"},
        {"item": "Smoked Gouda", "why": "Mild smokiness complements the smooth, mellow profile"},
    ],
}

_FOOD_DEFAULT = [
    {"item": "Dark Chocolate", "why": "A universal whiskey companion — cocoa and oak always work"},
    {"item": "Aged Cheese", "why": "Sharp, complex cheese matches whiskey's depth"},
    {"item": "Nuts (Almonds & Pecans)", "why": "Toasty, nutty flavors echo oak barrel notes"},
    {"item": "Charcuterie", "why": "Cured meats provide savory contrast to whiskey's sweetness"},
]

_COCKTAILS_BY_CATEGORY = {
    "bourbon": [
        {"name": "Old Fashioned", "ingredients": "2oz bourbon, sugar cube, 2 dashes Angostura bitters, orange peel", "desc": "The quintessential bourbon cocktail — simple and timeless"},
        {"name": "Mint Julep", "ingredients": "2.5oz bourbon, fresh mint, 0.5oz simple syrup, crushed ice", "desc": "Cool, refreshing, and perfect for warm weather sipping"},
        {"name": "Whiskey Sour", "ingredients": "2oz bourbon, 1oz lemon juice, 0.75oz simple syrup, egg white (optional)", "desc": "Tart, sweet, and silky — a perfect gateway cocktail"},
    ],
    "scotch": [
        {"name": "Rob Roy", "ingredients": "2oz scotch, 1oz sweet vermouth, 2 dashes Angostura bitters", "desc": "Scotland's answer to the Manhattan — smoky and sophisticated"},
        {"name": "Penicillin", "ingredients": "2oz blended scotch, 0.75oz lemon, 0.75oz honey-ginger syrup, Islay scotch float", "desc": "A modern classic — smoky, sweet, and citrusy"},
        {"name": "Blood & Sand", "ingredients": "0.75oz scotch, 0.75oz sweet vermouth, 0.75oz Cherry Heering, 0.75oz orange juice", "desc": "A Prohibition-era cocktail with a fruity, complex profile"},
    ],
    "irish": [
        {"name": "Irish Coffee", "ingredients": "1.5oz Irish whiskey, hot coffee, 1tsp brown sugar, whipped cream", "desc": "Warm, comforting, and deceptively strong"},
        {"name": "Tipperary", "ingredients": "1.5oz Irish whiskey, 1oz sweet vermouth, 0.5oz green Chartreuse", "desc": "Herbal and elegant — a forgotten classic worth reviving"},
    ],
    "japanese": [
        {"name": "Highball", "ingredients": "2oz Japanese whisky, 4oz very cold soda water, ice", "desc": "The Japanese serve — simple, refreshing, and the best way to honor the whisky"},
        {"name": "Mizuwari", "ingredients": "1.5oz Japanese whisky, mineral water, large ice", "desc": "Gently diluted to unlock subtle flavors — a contemplative serve"},
    ],
    "rye": [
        {"name": "Manhattan", "ingredients": "2oz rye, 1oz sweet vermouth, 2 dashes Angostura bitters, cherry", "desc": "The king of cocktails — rye's spice is essential here"},
        {"name": "Sazerac", "ingredients": "2oz rye, sugar cube, Peychaud's bitters, absinthe rinse, lemon peel", "desc": "New Orleans in a glass — bold, aromatic, and complex"},
        {"name": "Boulevardier", "ingredients": "1.5oz rye, 1oz sweet vermouth, 1oz Campari", "desc": "A Negroni's whiskey cousin — bitter, sweet, and spicy"},
    ],
    "canadian": [
        {"name": "Canadian Cocktail", "ingredients": "2oz Canadian whisky, 0.5oz Cointreau, 1 dash Angostura, 1tsp simple syrup", "desc": "Smooth and orange-accented — lets the whisky shine"},
        {"name": "Whisky Ginger", "ingredients": "2oz Canadian whisky, ginger ale, lime wedge", "desc": "The easiest crowd-pleaser — light, refreshing, and universally loved"},
    ],
}

_COCKTAILS_DEFAULT = [
    {"name": "Old Fashioned", "ingredients": "2oz whiskey, sugar cube, 2 dashes Angostura bitters, orange peel", "desc": "Works with almost any whiskey — the timeless classic"},
    {"name": "Whiskey Sour", "ingredients": "2oz whiskey, 1oz lemon juice, 0.75oz simple syrup", "desc": "Bright and balanced — a great starting point for any bottle"},
    {"name": "Highball", "ingredients": "2oz whiskey, 4oz soda water, ice", "desc": "Simple and refreshing — lets the whiskey's character come through"},
]


@router.get("/{whiskey_id}")
def get_pairings(whiskey_id: int, db: Session = Depends(get_db)):
    """Return food pairings and cocktail suggestions for a whiskey."""
    whiskey = db.query(models.Whiskey).filter(models.Whiskey.id == whiskey_id).first()
    if not whiskey:
        raise HTTPException(status_code=404, detail="Whiskey not found")

    cat = (whiskey.category or "").lower()

    food = _FOOD_BY_CATEGORY.get(cat, _FOOD_DEFAULT)
    cocktails = _COCKTAILS_BY_CATEGORY.get(cat, _COCKTAILS_DEFAULT)

    # Add a flavor-specific bonus pairing if we have flavor data
    profile = (whiskey.flavor_profile or "").lower()
    bonus = []
    if "smoky" in profile or "peaty" in profile:
        bonus.append({"item": "Grilled Steak", "why": "Char and smoke on meat mirrors the whiskey's campfire character"})
    if "honey" in profile or "sweet" in profile:
        bonus.append({"item": "Baklava", "why": "Layered honey and nut pastry amplifies the whiskey's natural sweetness"})
    if "fruity" in profile or "citrus" in profile:
        bonus.append({"item": "Fresh Fruit & Cream", "why": "Fresh berries or citrus segments echo the whiskey's bright notes"})
    if "spicy" in profile:
        bonus.append({"item": "Szechuan Peppercorn Dishes", "why": "Spice on spice creates an exciting, tingling pairing"})

    return {
        "whiskey_id": whiskey.id,
        "whiskey_name": whiskey.name,
        "category": whiskey.category,
        "food_pairings": food + bonus[:2],  # max 2 bonus
        "cocktails": cocktails,
    }
