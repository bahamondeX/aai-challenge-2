<script lang="ts" setup>
import type { DrawerDescriptionProps } from 'vaul-vue'
import type { HTMLAttributes } from 'vue'
import { reactiveOmit } from '@vueuse/core'
import { DrawerDescription } from 'vaul-vue'
import { cn } from '~/lib/utils'

const props = defineProps<DrawerDescriptionProps & { class?: HTMLAttributes['class'] }>()

const delegatedProps = reactiveOmit(props, 'class')
</script>

<template>
  <DrawerDescription v-bind="delegatedProps" :class="cn('text-sm text-muted-foreground', props.class)">
    <slot />
  </DrawerDescription>
</template>
