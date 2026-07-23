import React, { useState } from 'react'
import { View, Text, StyleSheet, Pressable, Alert } from 'react-native'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import * as DocumentPicker from 'expo-document-picker'
import { Trash2, UploadCloud, Image as ImageIcon } from 'lucide-react-native'
import Screen from '../components/Screen'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'
import DocumentRow from '../components/DocumentRow'
import {
  fetchDocuments, fetchPools, uploadWithProgress, deleteDocument,
  IMAGE_MIME_TYPES, DOCUMENT_MIME_TYPES, type Doc,
} from '../api/documents'
import { useAuthStore } from '../stores/authStore'
import { colors, fonts, radius } from '../theme/tokens'

export default function KnowledgeScreen() {
  const qc = useQueryClient()
  const refreshUser = useAuthStore((s) => s.hydrate)
  const docsQ = useQuery({ queryKey: ['documents'], queryFn: fetchDocuments })
  const poolsQ = useQuery({ queryKey: ['pools'], queryFn: fetchPools })

  const [uploading, setUploading] = useState(false)
  const [isImage, setIsImage] = useState(false)
  const [progressPct, setProgressPct] = useState(0)
  const [progressMessage, setProgressMessage] = useState('')

  async function refresh() {
    await Promise.all([qc.invalidateQueries({ queryKey: ['documents'] }), qc.invalidateQueries({ queryKey: ['pools'] })])
    refreshUser()
  }

  async function upload() {
    const res = await DocumentPicker.getDocumentAsync({
      type: [...DOCUMENT_MIME_TYPES, ...IMAGE_MIME_TYPES],
      copyToCacheDirectory: true,
    })
    if (res.canceled || !res.assets?.length) return
    const f = res.assets[0]
    setUploading(true)
    setIsImage(IMAGE_MIME_TYPES.includes(f.mimeType || ''))
    setProgressPct(0)
    setProgressMessage('Uploading…')
    try {
      await uploadWithProgress({ uri: f.uri, name: f.name, mimeType: f.mimeType }, '', {
        onProgress: (p) => { setProgressPct(p.progress); setProgressMessage(p.message) },
        onDone: (p) => { setProgressPct(p.progress); setProgressMessage(p.message) },
        onError: () => {},
      })
      refresh()
    } catch (e: any) {
      Alert.alert('Upload failed', e.message || 'Please try again.')
    } finally {
      setUploading(false)
    }
  }

  function confirmDelete(doc: Doc) {
    Alert.alert('Delete document?', `"${doc.file_name}" will be removed permanently.`, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: async () => { await deleteDocument(doc.file_name, doc.pool); refresh() } },
    ])
  }

  const docs = docsQ.data?.documents ?? []
  const grouped: Record<string, Doc[]> = {}
  for (const d of docs) (grouped[d.pool] ||= []).push(d)

  return (
    <Screen>
      <Text style={styles.title}>Knowledge Base</Text>

      <Card style={{ alignItems: 'center', gap: 10 }}>
        <View style={styles.uploadChip}>
          {isImage && uploading
            ? <ImageIcon color={colors.indigo} size={26} />
            : <UploadCloud color={colors.indigo} size={26} />}
        </View>
        <Text style={styles.uploadHint}>PDF, DOCX, TXT, CSV, MD, HTML, JSON, XML, PNG, JPG, WEBP, GIF, BMP, TIFF</Text>
        {uploading ? (
          <View style={{ alignSelf: 'stretch', gap: 6 }}>
            <View style={styles.progressRow}>
              <Text style={styles.progressLabel} numberOfLines={1}>{progressMessage || 'Uploading…'}</Text>
              <Text style={styles.progressPct}>{progressPct}%</Text>
            </View>
            <View style={styles.progressTrack}>
              <View style={[styles.progressFill, { width: `${progressPct}%` }]} />
            </View>
          </View>
        ) : (
          <Button title="Upload a document" onPress={upload} style={{ alignSelf: 'stretch' }} />
        )}
      </Card>

      {docs.length === 0 ? (
        <Card><Text style={styles.empty}>No documents yet. Upload your first above.</Text></Card>
      ) : (
        Object.entries(grouped).sort((a, b) => a[0].localeCompare(b[0])).map(([pool, list]) => (
          <Card key={pool}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <Text style={styles.pool}>{pool}</Text>
              <Badge label={String(list.length)} color="indigo" />
            </View>
            {list.map((d) => (
              <View key={d.key} style={styles.rowWrap}>
                <View style={{ flex: 1 }}><DocumentRow doc={d} /></View>
                <Pressable onPress={() => confirmDelete(d)} hitSlop={10}><Trash2 color={colors.inkMuted} size={18} /></Pressable>
              </View>
            ))}
          </Card>
        ))
      )}
    </Screen>
  )
}

const styles = StyleSheet.create({
  title: { fontFamily: fonts.display, fontSize: 24, color: colors.ink },
  uploadChip: { width: 52, height: 52, borderRadius: 16, backgroundColor: colors.indigoSoft, alignItems: 'center', justifyContent: 'center' },
  uploadHint: { fontFamily: fonts.body, fontSize: 12, color: colors.inkSoft },
  empty: { fontFamily: fonts.body, fontSize: 13, color: colors.inkSoft },
  pool: { fontFamily: fonts.displaySemi, fontSize: 15, color: colors.ink },
  rowWrap: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  progressRow: { flexDirection: 'row', justifyContent: 'space-between', gap: 8 },
  progressLabel: { flex: 1, fontFamily: fonts.body, fontSize: 12, color: colors.inkSoft },
  progressPct: { fontFamily: fonts.mono, fontSize: 12, color: colors.inkSoft },
  progressTrack: { height: 6, borderRadius: 3, backgroundColor: colors.surfaceAlt, overflow: 'hidden' },
  progressFill: { height: '100%', borderRadius: 3, backgroundColor: colors.indigo },
})
