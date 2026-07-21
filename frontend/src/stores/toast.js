import { defineStore } from 'pinia'

let nextId = 1

export const useToastStore = defineStore('toast', {
  state: () => ({ toasts: [] }),
  actions: {
    push(message, type = 'info') {
      const id = nextId++
      this.toasts.push({ id, message, type })
      setTimeout(() => this.dismiss(id), 4000)
      return id
    },
    success(message) { return this.push(message, 'success') },
    error(message) { return this.push(message, 'error') },
    dismiss(id) {
      this.toasts = this.toasts.filter((t) => t.id !== id)
    },
  },
})
