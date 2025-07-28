export function float32To16LEPCM(float32Array: Float32Array): Uint8Array {
	const pcm = new Int16Array(float32Array.length)
	for (let i = 0; i < float32Array.length; i++) {
		const s = Math.max(-1, Math.min(1, float32Array[i]))
		pcm[i] = s < 0 ? s * 0x8000 : s * 0x7fff
	}
	return new Uint8Array(pcm.buffer)
}