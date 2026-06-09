import { createServer } from 'http'
import { URL } from 'url'
import { search } from 'leboncoin-api-search'

const PORT = process.env.LBC_PORT || 3001

createServer(async (req, res) => {
  if (req.method !== 'GET') { res.writeHead(405); res.end(); return }

  const url = new URL(req.url!, `http://localhost:${PORT}`)
  if (url.pathname !== '/search') { res.writeHead(404); res.end(); return }

  const p = url.searchParams
  const query    = p.get('query') || ''
  const brand    = p.get('brand')       // ex: 'porsche'
  const model    = p.get('model')       // ex: 'cayenne'
  const yearMin  = p.get('year_min')
  const yearMax  = p.get('year_max')
  const kmMax    = p.get('km_max')
  const priceMin = p.get('price_min')
  const priceMax = p.get('price_max')

  if (!query && !brand) {
    res.writeHead(400, { 'Content-Type': 'application/json' })
    res.end(JSON.stringify({ error: 'query or brand required' }))
    return
  }

  try {
    const params: any = {
      category: '2',
      limit: 35,
    }

    if (query) params.keywords = query

    // Filtres enum : marque + modèle LBC
    if (brand || model) {
      params.enums = {}
      if (brand) params.enums.brand = [brand]
      if (model) params.enums.model = [model]
    }

    // Filtres ranges : année + km
    const ranges: any = {}
    if (yearMin || yearMax) {
      ranges.regdate = {}
      if (yearMin) ranges.regdate.min = parseInt(yearMin)
      if (yearMax) ranges.regdate.max = parseInt(yearMax)
    }
    if (kmMax) {
      ranges.mileage = { max: parseInt(kmMax) }
    }
    if (Object.keys(ranges).length) params.ranges = ranges

    if (priceMin) params.price_min = parseInt(priceMin)
    if (priceMax) params.price_max = parseInt(priceMax)

    const raw = await search(params)
    const ads = (raw?.ads || []).slice(0, 20).map((ad: any) => ({
      id: ad.list_id,
      title: ad.subject,
      price: ad.price?.[0] ?? null,
      url: ad.url,
      city: ad.location?.city ?? null,
      mileage: ad.attributes?.find((a: any) => a.key === 'mileage')?.value_label ?? null,
      year: ad.attributes?.find((a: any) => a.key === 'regdate')?.value_label ?? null,
      fuel: ad.attributes?.find((a: any) => a.key === 'fuel')?.value_label ?? null,
      image: ad.images?.thumb_url ?? null,
      date: ad.first_publication_date ?? null,
    }))

    const prices = ads.map((a: any) => a.price).filter((p: any) => p !== null && p > 0)
    const avg = prices.length ? Math.round(prices.reduce((a: number, b: number) => a + b, 0) / prices.length) : null
    const min = prices.length ? Math.min(...prices) : null
    const max = prices.length ? Math.max(...prices) : null

    res.writeHead(200, { 'Content-Type': 'application/json' })
    res.end(JSON.stringify({ ads, stats: { avg, min, max, count: ads.length, total: raw?.total ?? 0 } }))
  } catch (e: any) {
    res.writeHead(500, { 'Content-Type': 'application/json' })
    res.end(JSON.stringify({ error: e.message }))
  }
}).listen(PORT, () => console.log(`LBC service listening on port ${PORT}`))
