const API_BASE = 'https://zilloader.onrender.com'

const form = document.getElementById('analysis-form')
const statusEl = document.getElementById('status')
const resultsEl = document.getElementById('results')
const listingCountEl = document.getElementById('listing-count')
const averagePriceEl = document.getElementById('average-price')
const averageSqftEl = document.getElementById('average-sqft')
const undervaluedCountEl = document.getElementById('undervalued-count')
const excelLinkEl = document.getElementById('excel-link')
const csvLinkEl = document.getElementById('csv-link')
const chartEl = document.getElementById('chart')
const propertyListEl = document.getElementById('property-list')

function formatCurrency(value) {
  if (value === null || value === undefined) return 'N/A'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0
  }).format(value)
}

function formatNumber(value) {
  if (value === null || value === undefined) return 'N/A'
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(value)
}

form.addEventListener('submit', async event => {
  event.preventDefault()
  resultsEl.classList.add('hidden')
  propertyListEl.innerHTML = ''
  statusEl.textContent = 'Running analysis...'

  const city = document.getElementById('city').value.trim()
  const state = document.getElementById('state').value.trim().toUpperCase()
  const zipcode = document.getElementById('zipcode').value.trim()

  try {
    const response = await fetch(`${API_BASE}/analyze`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ city, state, zipcode })
    })

    if (!response.ok) {
      throw new Error('Analysis failed')
    }

    const data = await response.json()

    listingCountEl.textContent = formatNumber(data.listing_count)
    averagePriceEl.textContent = formatCurrency(data.average_price)
    averageSqftEl.textContent = formatNumber(data.average_sqft)
    undervaluedCountEl.textContent = formatNumber(data.undervalued_count)

    excelLinkEl.href = `${API_BASE}/${data.excel_file}`
    csvLinkEl.href = `${API_BASE}/${data.csv_file}`
    chartEl.src = `${API_BASE}/${data.chart_file}`

    for (const property of data.top_undervalued) {
      const div = document.createElement('div')
      div.className = 'property-item'
      div.innerHTML = `
        <div><strong>${property.address}</strong></div>
        <div>Price: ${formatCurrency(property.price)}</div>
})