<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import * as d3 from 'd3'
import * as documentsApi from '../api/documents.js'
import * as billingApi from '../api/billing.js'
import { useToastStore } from '../stores/toast.js'
import Card from '../components/ui/Card.vue'
import Button from '../components/ui/Button.vue'
import { Share2, Lock, RefreshCw, Locate } from 'lucide-vue-next'

const toast = useToastStore()
const router = useRouter()

const allowed = ref(true)          // knowledge_graph plan feature
const loading = ref(true)
const graphLoading = ref(false)
const pools = ref([])
const selectedPool = ref('')
const graph = ref({ nodes: [], edges: [] })
const highlightId = ref('')
const repulsion = ref(280)         // maps to the d3 charge-force strength

const svgRef = ref(null)
let simulation = null
let sel = null                     // { node, link, label } d3 selections
let zoomBehavior = null
let svgSelection = null

const INDIGO = '#6366F1'
const PINK = '#EC4899'
const INK_MUTED = '#A8A5BD'
const BORDER = '#EEECF7'

const hasGraph = computed(() => graph.value.nodes.length > 0)

async function init() {
  loading.value = true
  try {
    const [poolRes, sub] = await Promise.all([documentsApi.fetchPools(), billingApi.fetchSubscription()])
    allowed.value = sub.features?.knowledge_graph !== false
    pools.value = poolRes.pools || []
    if (pools.value.length && !selectedPool.value) selectedPool.value = pools.value[0].name
    if (allowed.value && selectedPool.value) await loadGraph()
  } catch (e) {
    toast.error(e.message || 'Could not load the knowledge graph')
  } finally {
    loading.value = false
  }
}

async function loadGraph() {
  if (!allowed.value || !selectedPool.value) return
  graphLoading.value = true
  try {
    graph.value = await documentsApi.fetchPoolGraph(selectedPool.value)
    highlightId.value = ''
    await nextTick()
    render()
  } catch (e) {
    if (e.status === 403) { allowed.value = false; return }
    toast.error(e.message || 'Could not load the graph')
  } finally {
    graphLoading.value = false
  }
}

function stopSim() {
  if (simulation) { simulation.stop(); simulation = null }
}

function render() {
  stopSim()
  const svgEl = svgRef.value
  if (!svgEl || !hasGraph.value) return

  const width = svgEl.clientWidth || 800
  const height = svgEl.clientHeight || 520
  const svg = d3.select(svgEl)
  svg.selectAll('*').remove()

  // d3-force mutates the objects it's given — copy so a re-render / reactive
  // read never trips over d3's injected x/y/vx/vy fields.
  const nodes = graph.value.nodes.map((n) => ({ ...n }))
  const links = graph.value.edges.map((e) => ({ ...e }))

  const container = svg.append('g')
  zoomBehavior = d3.zoom().scaleExtent([0.2, 4]).on('zoom', (event) => container.attr('transform', event.transform))
  svg.call(zoomBehavior)
  svgSelection = svg

  const link = container.append('g')
    .attr('stroke', INK_MUTED).attr('stroke-opacity', 0.5)
    .selectAll('line').data(links).join('line').attr('stroke-width', 1.5)

  const node = container.append('g')
    .selectAll('circle').data(nodes).join('circle')
    .attr('r', (d) => 8 + Math.min(d.source_count || 1, 6) * 2)
    .attr('fill', INDIGO).attr('stroke', '#fff').attr('stroke-width', 2)
    .style('cursor', 'pointer')
    .on('click', (_e, d) => { highlightId.value = highlightId.value === d.id ? '' : d.id; applyHighlight() })
    .call(d3.drag()
      .on('start', (event, d) => { if (!event.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y })
      .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y })
      .on('end', (event, d) => { if (!event.active) simulation.alphaTarget(0); d.fx = null; d.fy = null }))

  node.append('title').text((d) => `${d.label} · in ${d.source_count} document(s)`)

  const label = container.append('g')
    .selectAll('text').data(nodes).join('text')
    .text((d) => (d.label.length > 22 ? d.label.slice(0, 21) + '…' : d.label))
    .attr('font-size', 11).attr('fill', '#1E1B2E')
    .attr('dx', 12).attr('dy', 4).style('pointer-events', 'none')
    // White halo keeps overlapping labels legible on dense graphs.
    .attr('stroke', '#fff').attr('stroke-width', 3).style('paint-order', 'stroke')
    .attr('stroke-linejoin', 'round')

  simulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(links).id((d) => d.id).distance(90))
    .force('charge', d3.forceManyBody().strength(-repulsion.value))
    .force('center', d3.forceCenter(width / 2, height / 2))
    // Larger than the node's own radius so labels get real breathing room —
    // pure charge repulsion alone let nodes (and their labels) drift too
    // close together on a dense graph.
    .force('collide', d3.forceCollide().radius(46))
    .on('tick', () => {
      link.attr('x1', (d) => d.source.x).attr('y1', (d) => d.source.y)
        .attr('x2', (d) => d.target.x).attr('y2', (d) => d.target.y)
      node.attr('cx', (d) => d.x).attr('cy', (d) => d.y)
      label.attr('x', (d) => d.x).attr('y', (d) => d.y)
    })

  sel = { node, link, label, links }
  applyHighlight()
}

function applyHighlight() {
  if (!sel) return
  const id = highlightId.value
  if (!id) {
    sel.node.attr('fill', INDIGO).attr('opacity', 1)
    sel.link.attr('stroke', INK_MUTED).attr('stroke-opacity', 0.5)
    sel.label.style('display', null)
    return
  }
  const neighbors = new Set([id])
  sel.links.forEach((l) => {
    const s = l.source.id ?? l.source, t = l.target.id ?? l.target
    if (s === id) neighbors.add(t)
    if (t === id) neighbors.add(s)
  })
  sel.node
    .attr('fill', (d) => (d.id === id ? PINK : neighbors.has(d.id) ? INDIGO : INK_MUTED))
    .attr('opacity', (d) => (neighbors.has(d.id) ? 1 : 0.25))
  sel.link.attr('stroke', (l) => {
    const s = l.source.id ?? l.source, t = l.target.id ?? l.target
    return s === id || t === id ? PINK : INK_MUTED
  }).attr('stroke-opacity', (l) => {
    const s = l.source.id ?? l.source, t = l.target.id ?? l.target
    return s === id || t === id ? 0.9 : 0.1
  })
  // Only the focused node + its neighbours keep labels — declutters a dense graph.
  sel.label.style('display', (d) => (neighbors.has(d.id) ? null : 'none'))
}

function onRepulsionInput() {
  if (simulation) {
    simulation.force('charge', d3.forceManyBody().strength(-repulsion.value))
    simulation.alpha(0.5).restart()
  }
}

function goToBilling() {
  router.push('/billing')
}

function recenter() {
  if (zoomBehavior && svgSelection) {
    svgSelection.transition().duration(300).call(zoomBehavior.transform, d3.zoomIdentity)
  }
}

onMounted(init)
onBeforeUnmount(stopSim)
</script>

<template>
  <div class="flex flex-col gap-6">
    <div class="flex items-center gap-3">
      <span class="inline-flex items-center justify-center w-10 h-10 rounded-xl vaultly-gradient text-white">
        <Share2 class="w-5 h-5" />
      </span>
      <div>
        <h1 class="text-2xl font-bold font-display text-ink">Knowledge Graph</h1>
        <p class="text-sm text-ink-soft">Concepts and relationships found across a pool's documents.</p>
      </div>
    </div>

    <!-- Free-tier lock / upsell -->
    <Card v-if="!loading && !allowed" class="flex flex-col items-center text-center gap-3 py-10">
      <span class="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-amber/10 text-amber">
        <Lock class="w-6 h-6" />
      </span>
      <h2 class="text-lg font-semibold text-ink">The Knowledge Graph is a Pro feature</h2>
      <p class="text-sm text-ink-soft max-w-md">
        Upgrade to <span class="font-semibold text-ink">Pro</span> to visualise how the concepts across your
        documents connect — and explore your knowledge base as an interactive graph.
      </p>
      <Button class="mt-1" @click="goToBilling">See plans</Button>
    </Card>

    <template v-else-if="!loading">
      <!-- Controls -->
      <Card class="flex flex-wrap items-end gap-4">
        <label class="flex flex-col gap-1 text-sm">
          <span class="font-medium text-ink-soft">Pool</span>
          <select v-model="selectedPool" @change="loadGraph"
            class="rounded-xl border border-border-subtle bg-surface px-3 py-2 text-sm text-ink min-w-[10rem]">
            <option v-for="p in pools" :key="p.name" :value="p.name">{{ p.name }}</option>
          </select>
        </label>

        <label class="flex flex-col gap-1 text-sm" :class="!hasGraph && 'opacity-50'">
          <span class="font-medium text-ink-soft">Highlight concept</span>
          <select v-model="highlightId" :disabled="!hasGraph" @change="applyHighlight"
            class="rounded-xl border border-border-subtle bg-surface px-3 py-2 text-sm text-ink min-w-[12rem]">
            <option value="">— none —</option>
            <option v-for="n in graph.nodes" :key="n.id" :value="n.id">{{ n.label }}</option>
          </select>
        </label>

        <label class="flex flex-col gap-1 text-sm flex-1 min-w-[12rem]" :class="!hasGraph && 'opacity-50'">
          <span class="font-medium text-ink-soft">Node repulsion force</span>
          <input type="range" min="60" max="600" step="20" v-model.number="repulsion"
            :disabled="!hasGraph" @input="onRepulsionInput" class="accent-indigo" />
        </label>

        <Button variant="secondary" :disabled="graphLoading" @click="loadGraph">
          <RefreshCw class="w-4 h-4" :class="graphLoading && 'animate-spin'" /> Refresh
        </Button>
      </Card>

      <!-- Graph canvas -->
      <Card class="p-0 overflow-hidden">
        <div class="relative">
          <svg ref="svgRef" class="w-full" style="height: 560px; display: block;"></svg>

          <button v-if="hasGraph" type="button" title="Recenter" @click="recenter"
            class="absolute right-3 bottom-3 w-9 h-9 rounded-full bg-surface border border-border-subtle shadow-sm flex items-center justify-center text-indigo hover:bg-indigo/5 cursor-pointer">
            <Locate class="w-4 h-4" />
          </button>

          <div v-if="!hasGraph && !graphLoading"
            class="absolute inset-0 flex flex-col items-center justify-center gap-2 text-center px-6">
            <Share2 class="w-8 h-8 text-ink-muted" />
            <p class="text-sm font-medium text-ink">No graph for this pool yet</p>
            <p class="text-xs text-ink-soft max-w-sm">
              Graphs are built automatically when you upload documents. Only files added after this feature
              launched are included — upload something to this pool to see its concepts here.
            </p>
          </div>

          <div v-if="graphLoading" class="absolute inset-0 flex items-center justify-center">
            <p class="text-sm text-ink-soft">Loading graph…</p>
          </div>
        </div>
      </Card>

      <p v-if="hasGraph" class="text-xs text-ink-muted text-center">
        {{ graph.nodes.length }} concept(s) · {{ graph.edges.length }} relationship(s) · drag to rearrange,
        scroll to zoom, click a node to focus its connections.
      </p>
    </template>
  </div>
</template>
