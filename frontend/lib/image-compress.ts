/** Resize/compress images before upload to stay under serverless body limits. */

export async function compressImageFile(
  file: File,
  maxWidth = 1200,
  maxBytes = 800_000,
): Promise<File> {
  if (!file.type.startsWith('image/')) {
    throw new Error('画像ファイルを選択してください')
  }

  const bitmap = await createImageBitmap(file)
  const scale = Math.min(1, maxWidth / Math.max(bitmap.width, bitmap.height))
  const width = Math.max(1, Math.round(bitmap.width * scale))
  const height = Math.max(1, Math.round(bitmap.height * scale))

  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('画像の処理に失敗しました')
  ctx.drawImage(bitmap, 0, 0, width, height)
  bitmap.close()

  let quality = 0.88
  let blob = await canvasToBlob(canvas, 'image/jpeg', quality)
  while (blob.size > maxBytes && quality > 0.45) {
    quality -= 0.08
    blob = await canvasToBlob(canvas, 'image/jpeg', quality)
  }

  if (blob.size > maxBytes) {
    throw new Error('画像が大きすぎます。別の画像をお試しください')
  }

  const baseName = file.name.replace(/\.[^.]+$/, '') || 'image'
  return new File([blob], `${baseName}.jpg`, { type: 'image/jpeg' })
}

function canvasToBlob(canvas: HTMLCanvasElement, type: string, quality: number): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error('画像の圧縮に失敗しました'))),
      type,
      quality,
    )
  })
}
