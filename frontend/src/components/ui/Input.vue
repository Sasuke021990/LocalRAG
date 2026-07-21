<script setup>
defineProps({
  modelValue: [String, Number],
  label: String,
  type: { type: String, default: 'text' },
  placeholder: String,
  autocomplete: String,
  required: Boolean,
})
defineEmits(['update:modelValue'])
</script>

<template>
  <label class="block">
    <span v-if="label" class="block text-sm font-medium text-ink-soft mb-1.5">{{ label }}</span>
    <input
      :type="type"
      :value="modelValue"
      :placeholder="placeholder"
      :autocomplete="autocomplete"
      :required="required"
      @input="$emit('update:modelValue', $event.target.value)"
      class="w-full rounded-xl border border-border-subtle bg-surface-alt px-4 py-2.5 text-sm text-ink placeholder:text-ink-muted transition-colors focus:border-indigo focus:bg-surface"
    />
  </label>
</template>
