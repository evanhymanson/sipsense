"""
Seed guided tasting journeys.

Usage:
    cd backend
    python3 -m scripts.seed_journeys
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import SessionLocal, engine, Base
from app import models

Base.metadata.create_all(bind=engine)

JOURNEYS = [
    {
        "slug": "bourbon-curious",
        "title": "Bourbon Curious",
        "description": "Five essential bourbons that take you from beginner-friendly to bold. Perfect for anyone starting their whiskey journey.",
        "category": "bourbon",
        "difficulty": "beginner",
        "image_emoji": "\U0001f33d",
        "steps": [
            {
                "whiskey_name": "Buffalo Trace",
                "lesson_text": "Bourbon must be made in the USA from at least 51% corn, aged in new charred oak barrels. Buffalo Trace is the perfect starting point — approachable, balanced, and affordable.",
                "tasting_prompt": "Notice the caramel sweetness on the nose. Take a small sip and let it coat your tongue. Can you taste vanilla? Oak? A hint of spice at the finish?",
            },
            {
                "whiskey_name": "Maker's Mark",
                "lesson_text": "Most bourbons use rye as their secondary grain, but Maker's Mark uses wheat instead. This creates a softer, sweeter profile. Wheated bourbons are a whole sub-category worth exploring.",
                "tasting_prompt": "Compare this to Buffalo Trace. Notice how it's smoother and sweeter? The wheat gives it a rounder, less spicy character. Look for honey and fruit notes.",
            },
            {
                "whiskey_name": "Woodford Reserve",
                "lesson_text": "Woodford Reserve is one of few bourbons that uses pot stills alongside column stills, and it's triple-distilled. This creates a more complex, layered spirit. Pay attention to how the production method affects flavor.",
                "tasting_prompt": "This is richer than the first two. Look for dark chocolate, dried fruit, and baking spices. The finish should be longer and more complex. Try adding a few drops of water — does it open up new flavors?",
            },
            {
                "whiskey_name": "Four Roses Single Barrel",
                "lesson_text": "Single barrel means every bottle comes from one individual barrel, so there's natural variation. Four Roses uses 10 different bourbon recipes (combinations of 2 mash bills and 5 yeast strains). This is craft bourbon at its finest.",
                "tasting_prompt": "At 100 proof, this has more intensity. Notice the rye spice coming through — black pepper, cinnamon. The fruit notes are more pronounced too. Compare the complexity to the blended bourbons you've tried.",
            },
            {
                "whiskey_name": "Wild Turkey 101",
                "lesson_text": "Wild Turkey 101 represents high-proof, no-nonsense bourbon. At 101 proof (50.5% ABV), it delivers bold flavor without breaking the bank. Many bartenders and bourbon enthusiasts consider this the best value in American whiskey.",
                "tasting_prompt": "The higher proof brings more intense flavors. Notice the rich caramel and vanilla, but also a peppery kick. Try it neat first, then with a splash of water. How does the proof affect your experience?",
            },
        ],
    },
    {
        "slug": "scotch-regions",
        "title": "Scotch Regions Tour",
        "description": "Travel across Scotland through five iconic single malts. Each region has its own character — from gentle Speyside to wild Islay.",
        "category": "scotch",
        "difficulty": "intermediate",
        "image_emoji": "\U0001f3f4\U000e0067\U000e0062\U000e0073\U000e0063\U000e0074\U000e007f",
        "steps": [
            {
                "whiskey_name": "Glenfiddich 12",
                "lesson_text": "Speyside is the heartland of Scotch whisky, home to over half of Scotland's distilleries. The region is known for elegant, fruity, and approachable malts. Glenfiddich 12 is the world's best-selling single malt.",
                "tasting_prompt": "Look for light fruit — pear, apple — along with gentle oak and a whisper of malt sweetness. This is the Speyside style: graceful and easy-drinking. Notice how different it is from bourbon.",
            },
            {
                "whiskey_name": "Glenmorangie 10",
                "lesson_text": "The Highlands is Scotland's largest whisky region, stretching from the central belt to the northern coast. Styles vary enormously, but Highland malts often show honey, heather, and gentle spice. Glenmorangie uses the tallest stills in Scotland for a lighter, more delicate spirit.",
                "tasting_prompt": "Notice the citrus notes — lemon, orange peel. There's a creamy, almost buttery texture. The finish is clean and refreshing. Compare the fruit character to Glenfiddich's — how are they different?",
            },
            {
                "whiskey_name": "Laphroaig 10",
                "lesson_text": "Welcome to Islay, the smoky island. Islay malts are dried over peat fires, infusing the barley with intense smoky, medicinal, and maritime flavors. Laphroaig is famously polarizing — people either love it or hate it. Prince Charles loves it enough to grant it a Royal Warrant.",
                "tasting_prompt": "This will be dramatically different from anything so far. Look for peat smoke, iodine, seaweed, and bandages (yes, really). Underneath the smoke, there's sweetness — vanilla, honey. Give it time; Islay malts often grow on you.",
            },
            {
                "whiskey_name": "Dalmore 12",
                "lesson_text": "Back to the Highlands, but a very different style. Dalmore uses sherry cask finishing — the whisky spends time in barrels that previously held Spanish sherry. This adds rich, dark fruit flavors and a luxurious texture.",
                "tasting_prompt": "Look for dried fruit — raisins, plums, orange marmalade. There should be chocolate and coffee notes from the sherry influence. Compare this richness to the lighter Highland style of Glenmorangie.",
            },
            {
                "whiskey_name": "Balvenie 12 DoubleWood",
                "lesson_text": "We finish back in Speyside with a twist. Balvenie DoubleWood is aged first in traditional oak, then finished in sherry casks. This 'double maturation' technique is now widespread, but Balvenie helped pioneer it. The distillery still has its own maltings floor and cooperage.",
                "tasting_prompt": "This combines the Speyside elegance you tasted in Glenfiddich with the sherry richness of Dalmore. Notice the layers — honey and vanilla from the first maturation, dried fruit and spice from the sherry finish. A beautiful synthesis of everything you've learned.",
            },
        ],
    },
    {
        "slug": "under-40",
        "title": "Under $40 Explorer",
        "description": "Proof that great whiskey doesn't require a big budget. Five bottles under $40 that punch well above their price.",
        "category": "exploration",
        "difficulty": "beginner",
        "image_emoji": "\U0001f4b0",
        "steps": [
            {
                "whiskey_name": "Buffalo Trace",
                "lesson_text": "At around $30, Buffalo Trace is widely considered the best value in bourbon. It's the flagship of the same distillery that makes Pappy Van Winkle, using similar production methods at a fraction of the price.",
                "tasting_prompt": "Sip this and think about value. This is a $30 bottle — does it taste like it costs more? Focus on the balance of sweetness, spice, and oak. Great value whiskey isn't about being cheap; it's about exceeding expectations.",
            },
            {
                "whiskey_name": "Rittenhouse Rye",
                "lesson_text": "Bottled-in-bond means it was made in a single season, at a single distillery, aged at least 4 years, and bottled at exactly 100 proof. It's a federal quality guarantee. At under $30, Rittenhouse is one of the best deals in American whiskey.",
                "tasting_prompt": "Notice how different rye tastes from bourbon — more herbal, spicier, drier. This is the backbone of classic cocktails like the Manhattan and Sazerac. Try it neat first, then consider how it would work in a cocktail.",
            },
            {
                "whiskey_name": "Jameson",
                "lesson_text": "Irish whiskey is triple-distilled (vs. typically twice for Scotch and bourbon), which creates a smoother, lighter spirit. Ireland's whiskey industry nearly died out in the 20th century but has seen a remarkable revival. Jameson leads that comeback.",
                "tasting_prompt": "Notice the smoothness compared to the American whiskeys. Irish whiskey tends to be lighter and more approachable. Look for green apple, vanilla, and a light nuttiness. The triple distillation gives it that clean, easy-drinking character.",
            },
            {
                "whiskey_name": "Suntory Toki",
                "lesson_text": "Japanese whisky was inspired by Scotch but has evolved its own identity — emphasizing harmony, balance, and precision. Suntory's founder Shinjiro Torii studied in Scotland before founding Japan's first distillery in 1923. Toki is a blend designed for everyday enjoyment.",
                "tasting_prompt": "This is deliberately light and clean — the Japanese highball (whisky + sparkling water) is a national obsession. Notice the floral and citrus notes. Try making a highball: fill a tall glass with ice, add one part Toki, three parts cold sparkling water.",
            },
            {
                "whiskey_name": "Wild Turkey 101",
                "lesson_text": "We end with proof that high-quality, high-proof bourbon doesn't need a high price tag. Wild Turkey has been making whiskey in Lawrenceburg, Kentucky since 1855. Master distiller Jimmy Russell has been there for over 60 years — longer than any other active distiller.",
                "tasting_prompt": "Compare this to your first Buffalo Trace. Both are Kentucky bourbons under $30, but they're quite different. Wild Turkey's higher proof and different mash bill create a bolder, spicier experience. Which style do you prefer?",
            },
        ],
    },
    {
        "slug": "smoke-peat",
        "title": "Smoke & Peat Deep Dive",
        "description": "For the bold and curious. Explore the world of peated whisky, from gentle smoke to full-on campfire intensity.",
        "category": "scotch",
        "difficulty": "intermediate",
        "image_emoji": "\U0001f525",
        "steps": [
            {
                "whiskey_name": "Laphroaig 10",
                "lesson_text": "Peat is decomposed vegetation — when burned, it creates the smoky flavors in Islay malts. Laphroaig dries its barley over peat fires in-house and uses water from peat bogs. The result is one of the most intensely flavored whiskeys in the world.",
                "tasting_prompt": "Don't fight the smoke — lean into it. After the initial peat blast, look for underlying sweetness: vanilla, honey, maybe some salt. Many people hate their first peated whisky but grow to love it. Keep an open mind.",
            },
            {
                "whiskey_name": "Ardbeg 10",
                "lesson_text": "Ardbeg is even more heavily peated than Laphroaig, but many find it more approachable because of its citrusy, sweet undertones. The distillery was nearly destroyed multiple times but was saved by devoted fans. It's now considered one of the world's finest.",
                "tasting_prompt": "Compare directly to Laphroaig. Ardbeg tends to be smokier but also sweeter and more citrusy. Look for lemon, lime, and dark chocolate alongside the peat. Notice how the smoke sits differently on your palate — is it more or less medicinal?",
            },
            {
                "whiskey_name": "Lagavulin 16",
                "lesson_text": "Lagavulin 16 is often called the pinnacle of Islay whisky. It's been aged much longer than the others (16 years vs. 10), which rounds out the peat and adds incredible depth. This is the whisky that Ron Swanson drinks on Parks and Recreation.",
                "tasting_prompt": "This is where it all comes together. The extra aging has mellowed the smoke into something rich and complex. Look for dried fruit, leather, dark chocolate, and a long, warming finish. Notice how the peat has integrated rather than dominated.",
            },
            {
                "whiskey_name": "Nikka From The Barrel",
                "lesson_text": "Surprise — peat isn't just for Scotland. Japanese distillers learned from Scottish masters and some produce excellent peated whisky. Nikka From The Barrel is a blended whisky at cask strength (~51% ABV) that shows how Japan puts its own spin on smoky whisky.",
                "tasting_prompt": "How does Japanese smoke compare to Islay? It tends to be more restrained and integrated. Look for the interplay of smoke with vanilla, caramel, and orchard fruit. The high proof means big flavor — add a few drops of water and notice what changes.",
            },
        ],
    },
    {
        "slug": "world-tour",
        "title": "World Whiskey Tour",
        "description": "One glass, five countries. Discover how geography, tradition, and culture shape whiskey around the globe.",
        "category": "exploration",
        "difficulty": "beginner",
        "image_emoji": "\U0001f30d",
        "steps": [
            {
                "whiskey_name": "Buffalo Trace",
                "lesson_text": "We start in Kentucky, USA — the birthplace of bourbon. American whiskey is defined by corn, new charred oak barrels, and a frontier spirit. Kentucky's limestone water, hot summers, and cold winters create the perfect conditions for bourbon maturation.",
                "tasting_prompt": "This is the taste of America. Sweet corn, vanilla from new oak, caramel from the char. Notice the sweetness — that's the corn and the new barrels. American whiskey is generally sweeter and bolder than its European and Asian counterparts.",
            },
            {
                "whiskey_name": "Glenfiddich 12",
                "lesson_text": "Scotland has been making whisky (no 'e') for over 500 years. Scotch must be aged at least 3 years in Scotland. Glenfiddich, meaning 'Valley of the Deer,' was one of the first single malts to be marketed internationally, helping change Scotch from a blend-dominated market.",
                "tasting_prompt": "Compare this to Buffalo Trace. Scotch uses malted barley instead of corn, and used (not new) barrels. Notice how it's lighter, more fruity, less sweet. The old-world restraint vs. new-world boldness is one of whiskey's great contrasts.",
            },
            {
                "whiskey_name": "Redbreast 12",
                "lesson_text": "Ireland may have invented whiskey — the word comes from the Irish 'uisce beatha' (water of life). Irish whiskey is typically triple-distilled and uses a mix of malted and unmalted barley (called 'pot still whiskey'). This creates a uniquely creamy, spicy character found nowhere else.",
                "tasting_prompt": "Redbreast is considered the gold standard of Irish pot still whiskey. Look for that distinctive creaminess, along with fruit (plum, cherry), spice (nutmeg, cinnamon), and a rich, oily texture. How does the triple distillation compare to Scotch and bourbon?",
            },
            {
                "whiskey_name": "Hibiki Harmony",
                "lesson_text": "Japan began making whisky in 1923 when Masataka Taketsuru returned from studying in Scotland. Japanese whisky emphasizes harmony (wa) — delicate balance over bold statement. Hibiki blends malt and grain whiskies from Suntory's three distilleries into something greater than its parts.",
                "tasting_prompt": "This is whisky as meditation. Notice the delicacy — rose petals, honey, white chocolate, a hint of sandalwood. Everything is in balance; nothing dominates. Compare this philosophy to bourbon's boldness and Scotch's tradition. Which approach resonates with you?",
            },
            {
                "whiskey_name": "Jameson",
                "lesson_text": "We close the tour back in Ireland with the world's most popular Irish whiskey. Jameson represents the spirit of Irish whiskey — welcoming, social, unpretentious. It's designed to be enjoyed by everyone, whether neat, on ice, or in a cocktail.",
                "tasting_prompt": "After tasting whiskey from four countries, return to Jameson with fresh eyes. What do you notice now that you wouldn't have before? Can you identify the Irish character — the smoothness, the lightness? Which country's style is your favorite? That's your starting point for deeper exploration.",
            },
        ],
    },
]


def seed():
    db = SessionLocal()

    for j_data in JOURNEYS:
        existing = db.query(models.Journey).filter(models.Journey.slug == j_data["slug"]).first()
        if existing:
            print(f"Journey '{j_data['slug']}' already exists, skipping")
            continue

        steps_data = j_data.pop("steps")

        journey = models.Journey(**j_data, bottle_count=len(steps_data))
        db.add(journey)
        db.flush()  # get journey.id

        for i, step_data in enumerate(steps_data, start=1):
            whiskey_name = step_data.pop("whiskey_name")
            whiskey = (
                db.query(models.Whiskey)
                .filter(models.Whiskey.name.ilike(f"%{whiskey_name}%"))
                .first()
            )
            if not whiskey:
                print(f"  WARNING: Whiskey '{whiskey_name}' not found, skipping step {i}")
                continue

            step = models.JourneyStep(
                journey_id=journey.id,
                step_number=i,
                whiskey_id=whiskey.id,
                **step_data,
            )
            db.add(step)

        db.commit()
        print(f"Seeded journey: {journey.title} ({journey.bottle_count} steps)")

    db.close()


if __name__ == "__main__":
    seed()
