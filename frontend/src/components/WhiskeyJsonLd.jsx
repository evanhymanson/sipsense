import { Helmet } from 'react-helmet-async'

export default function WhiskeyJsonLd({ whiskey }) {
  const schema = {
    '@context': 'https://schema.org',
    '@type': 'Product',
    name: whiskey.name,
    brand: { '@type': 'Brand', name: whiskey.distillery },
    description: whiskey.description || `${whiskey.name} by ${whiskey.distillery}`,
    category: `Whiskey > ${whiskey.category}`,
    ...(whiskey.image_url && {
      image: whiskey.image_url.startsWith('http')
        ? whiskey.image_url
        : `https://sipsense.ai${whiskey.image_url}`,
    }),
    ...(whiskey.price_usd && {
      offers: {
        '@type': 'Offer',
        price: whiskey.price_usd,
        priceCurrency: 'USD',
        availability: 'https://schema.org/InStock',
      },
    }),
    ...(whiskey.rating_count > 0 && {
      aggregateRating: {
        '@type': 'AggregateRating',
        ratingValue: whiskey.rating_avg,
        bestRating: 5,
        worstRating: 1,
        ratingCount: whiskey.rating_count,
      },
    }),
    additionalProperty: [
      ...(whiskey.abv ? [{ '@type': 'PropertyValue', name: 'ABV', value: `${whiskey.abv}%` }] : []),
      ...(whiskey.age ? [{ '@type': 'PropertyValue', name: 'Age Statement', value: `${whiskey.age} Years` }] : []),
      ...(whiskey.region ? [{ '@type': 'PropertyValue', name: 'Region', value: whiskey.region }] : []),
    ].filter(Boolean),
  }
  if (schema.additionalProperty.length === 0) delete schema.additionalProperty
  return (
    <Helmet>
      <script type="application/ld+json">{JSON.stringify(schema)}</script>
    </Helmet>
  )
}
