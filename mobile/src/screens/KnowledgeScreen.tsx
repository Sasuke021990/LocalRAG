import React, { useCallback, useState } from 'react'
import { View, Text, StyleSheet, Pressable, Alert } from 'react-native'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useFocusEffect } from '@react-navigation/native'
import * as DocumentPicker from 'expo-document-picker'
import { Trash2, UploadCloud, Image as ImageIcon, Plus, ChevronDown, AlertCircle } from 'lucide-react-native'
import Screen from '../components/Screen'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'
import DocumentRow from '../components/DocumentRow'
import PoolPickerSheet from '../components/PoolPickerSheet'
import Skeleton from '../components/Skeleton'
import {
  fetchDocuments, fetchPools, uploadWithProgress, deleteDocument, moveDocument, deletePool,
  IMAGE_MIME_TYPES, DOCUMENT_MIME_TYPES, type Doc,
} from '../api/documents'
import { useAuthStore } from '../stores/authStore'
import { useAppTheme } from '../theme/ThemeContext'
import { tapLight, tapMedium, notifySuccess, notifyError } from '../utils/haptics'
import { fonts, radius } from '../theme/tokens'

// What the pool-picker sheet is currently open for -- one shared sheet
// instance handles upload destination, move, "needs a pool" assignment, and
// dedicated pool creation (mirrors web's single PoolPicker.vue reused across
// the upload form and the move modal).
type PickerTarget = 'upload' | 'newpool' | { doc: Doc } | null

export default function KnowledgeScreen() {
  const qc = useQueryClient()
  const { colors } = useAppTheme()
  const refreshUser = useAuthStore((s) => s.hydrate)
  const docsQ = useQuery({ queryKey: ['documents'], queryFn: fetchDocuments })
  const poolsQ = useQuery({ queryKey: ['pools'], queryFn: fetchPools })

  const [uploading, setUploading] = useState(false)
  const [isImage, setIsImage] = useState(false)
  const [progressPct, setProgressPct] = useState(0)
  const [progressMessage, setProgressMessage] = useState('')
  const [uploadPool, setUploadPool] = useState('')
  const [picker, setPicker] = useState<PickerTarget>(null)
  const [refreshing, setRefreshing] = useState(false)

  async function refresh() {
    await Promise.all([qc.invalidateQueries({ queryKey: ['documents'] }), qc.invalidateQueries({ queryKey: ['pools'] })])
    refreshUser()
  }

  async function onRefresh() {
    setRefreshing(true)
    await refresh()
    setRefreshing(false)
  }

  // Summaries and graph data can finish their background pass (task.md
  // §1a/§1d) while the user is elsewhere -- refetch whenever this screen
  // regains focus so completed work shows up without a manual pull.
  useFocusEffect(useCallback(() => { docsQ.refetch(); poolsQ.refetch() }, []))

  async function upload() {
    const res = await DocumentPicker.getDocumentAsync({
      type: [...DOCUMENT_MIME_TYPES, ...IMAGE_MIME_TYPES],
      copyToCacheDirectory: true,
    })
    if (res.canceled || !res.assets?.length) return
    const f = res.assets[0]
    tapLight()
    setUploading(true)
    setIsImage(IMAGE_MIME_TYPES.includes(f.mimeType || ''))
    setProgressPct(0)
    setProgressMessage('Uploading…')
    try {
      let streamError = ''
      await uploadWithProgress({ uri: f.uri, name: f.name, mimeType: f.mimeType }, uploadPool, {
        onProgress: (p) => { setProgressPct(p.progress); setProgressMessage(p.message) },
        onDone: (p) => { setProgressPct(p.progress); setProgressMessage(p.message) },
        // The file itself uploaded fine if we got this far — only the
        // progress stream broke. Surface it instead of freezing the bar
        // mid-way with no explanation (task.md's silent-failure audit).
        onError: (e) => { streamError = e?.message || 'Lost track of processing progress.' },
      })
      setUploadPool('')
      refresh()
      if (streamError) {
        notifyError()
        Alert.alert(
          'Upload sent, but progress was lost',
          `${streamError}\n\nThe document is likely still processing — pull to refresh in a moment.`,
        )
      } else {
        // Processing a large document takes long enough that users look
        // away — the same reason the push notification exists.
        notifySuccess()
      }
    } catch (e: any) {
      notifyError()
      Alert.alert('Upload failed', e.message || 'Please try again.')
    } finally {
      setUploading(false)
    }
  }

  function confirmDelete(doc: Doc) {
    Alert.alert('Delete document?', `"${doc.file_name}" will be removed permanently.`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete', style: 'destructive',
        onPress: async () => { tapMedium(); await deleteDocument(doc.file_name, doc.pool); refresh() },
      },
    ])
  }

  function confirmDeletePool(name: string) {
    Alert.alert('Delete pool?', `"${name}" will be removed. It must already be empty.`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete', style: 'destructive',
        onPress: async () => {
          try { await deletePool(name); refresh() }
          catch (e: any) { Alert.alert('Could not delete pool', e?.message ?? 'Please try again.') }
        },
      },
    ])
  }

  async function movePickedTo(doc: Doc, newPool: string) {
    setPicker(null)
    if (!newPool || (newPool === doc.pool && doc.pool_assigned !== false)) return
    try {
      await moveDocument(doc.file_name, doc.pool, newPool || 'General')
      refresh()
    } catch (e: any) {
      Alert.alert('Could not move document', e?.message ?? 'Please try again.')
    }
  }

  const docs = docsQ.data?.documents ?? []
  const pools = poolsQ.data?.pools ?? []
  const unassigned = docs.filter((d) => d.pool_assigned === false)

  // Seed every known pool (so an empty one still renders its own card),
  // then bucket documents into them -- mirrors web's KnowledgeBasePage.vue.
  const grouped: Record<string, Doc[]> = {}
  for (const p of pools) grouped[p.name] = []
  for (const d of docs) (grouped[d.pool] ||= []).push(d)
  const groupedEntries = Object.entries(grouped).sort((a, b) => a[0].localeCompare(b[0]))

  return (
    <Screen refreshing={refreshing} onRefresh={onRefresh}>
      <View style={styles.headerRow}>
        <Text style={[styles.title, { color: colors.ink }]}>Knowledge Base</Text>
        <Pressable style={[styles.newPoolBtn, { borderColor: colors.indigo }]} onPress={() => setPicker('newpool')}>
          <Plus color={colors.indigo} size={16} />
          <Text style={[styles.newPoolBtnText, { color: colors.indigo }]}>New pool</Text>
        </Pressable>
      </View>

      <Card style={{ alignItems: 'center', gap: 10 }}>
        <View style={[styles.uploadChip, { backgroundColor: colors.indigoSoft }]}>
          {isImage && uploading
            ? <ImageIcon color={colors.indigo} size={26} />
            : <UploadCloud color={colors.indigo} size={26} />}
        </View>
        <Text style={[styles.uploadHint, { color: colors.inkSoft }]}>PDF, DOCX, TXT, CSV, MD, HTML, JSON, XML, PNG, JPG, WEBP, GIF, BMP, TIFF</Text>

        <Pressable
          style={[styles.poolRow, { borderColor: colors.border, backgroundColor: colors.surfaceAlt }]}
          onPress={() => setPicker('upload')}
          disabled={uploading}
        >
          <Text style={[styles.poolRowLabel, { color: colors.inkSoft }]}>Pool</Text>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
            <Text style={[styles.poolRowValue, { color: colors.ink }]}>{uploadPool || 'General (default)'}</Text>
            <ChevronDown color={colors.inkMuted} size={14} />
          </View>
        </Pressable>

        {uploading ? (
          <View style={{ alignSelf: 'stretch', gap: 6 }}>
            <View style={styles.progressRow}>
              <Text style={[styles.progressLabel, { color: colors.inkSoft }]} numberOfLines={1}>{progressMessage || 'Uploading…'}</Text>
              <Text style={[styles.progressPct, { color: colors.inkSoft }]}>{progressPct}%</Text>
            </View>
            <View style={[styles.progressTrack, { backgroundColor: colors.surfaceAlt }]}>
              <View style={[styles.progressFill, { backgroundColor: colors.indigo, width: `${progressPct}%` }]} />
            </View>
          </View>
        ) : (
          <Button title="Upload a document" onPress={upload} style={{ alignSelf: 'stretch' }} />
        )}
      </Card>

      {unassigned.length > 0 && (
        <Card style={[styles.unassignedCard, { borderColor: colors.amber, backgroundColor: colors.amberSoft }]}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <AlertCircle color={colors.amber} size={18} />
            <Text style={[styles.unassignedTitle, { color: colors.ink }]}>
              {unassigned.length} document{unassigned.length > 1 ? 's need' : ' needs'} a pool
            </Text>
          </View>
          {unassigned.map((d) => (
            <View key={d.key} style={styles.unassignedRow}>
              <Text style={[styles.unassignedName, { color: colors.ink }]} numberOfLines={1}>{d.file_name}</Text>
              <Pressable style={[styles.chooseBtn, { borderColor: colors.border }]} onPress={() => setPicker({ doc: d })}>
                <Text style={[styles.chooseBtnText, { color: colors.ink }]}>Choose a pool</Text>
              </Pressable>
            </View>
          ))}
        </Card>
      )}

      {docsQ.isLoading ? (
        // Previously this window rendered "No documents yet" — telling a user
        // with a full library that it was empty, until the fetch resolved.
        <Card style={{ gap: 14 }}>
          {[0, 1, 2].map((i) => (
            <View key={i} style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
              <Skeleton width={36} height={36} />
              <View style={{ flex: 1, gap: 6 }}>
                <Skeleton width="60%" height={13} />
                <Skeleton width="35%" height={11} />
              </View>
            </View>
          ))}
        </Card>
      ) : docs.length === 0 ? (
        <Card><Text style={[styles.empty, { color: colors.inkSoft }]}>No documents yet. Upload your first above.</Text></Card>
      ) : (
        groupedEntries.map(([pool, list]) => (
          <Card key={pool}>
            <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                <Text style={[styles.pool, { color: colors.ink }]}>{pool}</Text>
                <Badge label={String(list.length)} color="indigo" />
              </View>
              {list.length === 0 && pool !== 'General' ? (
                <Pressable onPress={() => confirmDeletePool(pool)} style={styles.deleteBtn} hitSlop={4}>
                  <Trash2 color={colors.rose} size={16} />
                </Pressable>
              ) : null}
            </View>
            {list.length === 0 ? (
              <Text style={[styles.empty, { color: colors.inkSoft }]}>Empty pool.</Text>
            ) : (
              list.map((d) => (
                <View key={d.key} style={styles.rowWrap}>
                  <View style={{ flex: 1 }}>
                    <DocumentRow doc={d} onMove={(doc) => setPicker({ doc })} />
                  </View>
                  {/* A real 40x40 target with its own gap from the move button
                      above -- both were 18px icons a few px apart, an easy
                      way to hit "delete" while reaching for "move" (task.md
                      P1 #15). */}
                  <Pressable onPress={() => confirmDelete(d)} style={styles.deleteBtn} hitSlop={4}>
                    <Trash2 color={colors.rose} size={18} />
                  </Pressable>
                </View>
              ))
            )}
          </Card>
        ))
      )}

      <PoolPickerSheet
        visible={picker === 'upload'}
        pools={pools}
        selected={uploadPool}
        allowEmpty
        title="Upload to pool"
        onChoose={(p) => { setUploadPool(p); setPicker(null) }}
        onDismiss={() => setPicker(null)}
        onCreated={refresh}
      />
      <PoolPickerSheet
        visible={picker === 'newpool'}
        pools={pools}
        selected=""
        allowEmpty={false}
        startInCreate
        title="Create a pool"
        onChoose={() => setPicker(null)}
        onDismiss={() => setPicker(null)}
        onCreated={refresh}
      />
      <PoolPickerSheet
        visible={typeof picker === 'object' && picker !== null}
        pools={pools}
        selected={typeof picker === 'object' && picker ? picker.doc.pool : ''}
        allowEmpty={false}
        title={typeof picker === 'object' && picker ? `Move "${picker.doc.file_name}"` : 'Move document'}
        onChoose={(p) => { if (typeof picker === 'object' && picker) movePickedTo(picker.doc, p) }}
        onDismiss={() => setPicker(null)}
        onCreated={refresh}
      />
    </Screen>
  )
}

const styles = StyleSheet.create({
  headerRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  title: { fontFamily: fonts.display, fontSize: 24 },
  newPoolBtn: { flexDirection: 'row', alignItems: 'center', gap: 5, borderWidth: 1, borderRadius: radius.md, paddingHorizontal: 12, paddingVertical: 7 },
  newPoolBtnText: { fontFamily: fonts.bodyMedium, fontSize: 13 },
  uploadChip: { width: 52, height: 52, borderRadius: 16, alignItems: 'center', justifyContent: 'center' },
  uploadHint: { fontFamily: fonts.body, fontSize: 12 },
  poolRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', alignSelf: 'stretch', borderWidth: 1, borderRadius: radius.md, paddingHorizontal: 12, paddingVertical: 10 },
  poolRowLabel: { fontFamily: fonts.bodyMedium, fontSize: 12 },
  poolRowValue: { fontFamily: fonts.bodyMedium, fontSize: 13 },
  empty: { fontFamily: fonts.body, fontSize: 13 },
  pool: { fontFamily: fonts.displaySemi, fontSize: 15 },
  rowWrap: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  deleteBtn: { width: 40, height: 40, alignItems: 'center', justifyContent: 'center' },
  progressRow: { flexDirection: 'row', justifyContent: 'space-between', gap: 8 },
  progressLabel: { flex: 1, fontFamily: fonts.body, fontSize: 12 },
  progressPct: { fontFamily: fonts.mono, fontSize: 12 },
  progressTrack: { height: 6, borderRadius: 3, overflow: 'hidden' },
  progressFill: { height: '100%', borderRadius: 3 },
  unassignedCard: { borderWidth: 1 },
  unassignedTitle: { fontFamily: fonts.bodySemi, fontSize: 14 },
  unassignedRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8, paddingVertical: 6 },
  unassignedName: { flex: 1, fontFamily: fonts.body, fontSize: 13 },
  chooseBtn: { borderWidth: 1, borderRadius: radius.md, paddingHorizontal: 10, paddingVertical: 6 },
  chooseBtnText: { fontFamily: fonts.bodyMedium, fontSize: 12 },
})
