<script setup lang="ts">
import type { HTMLAttributes } from 'vue'
import { reactiveOmit } from '@vueuse/core'
import {
  NavigationMenuViewport,
  type NavigationMenuViewportProps,
  useForwardProps,
} from 'reka-ui'
import { cn } from '~/lib/utils'

const props = defineProps<NavigationMenuViewportProps & { class?: HTMLAttributes['class'] }>()

const delegatedProps = reactiveOmit(props, 'class')

const forwardedProps = useForwardProps(delegatedProps)
</script>

<template>
  <div class="absolute left-0 top-full flex justify-center">
    <NavigationMenuViewport
      v-bind="forwardedProps"
      :class="
        cn(
          'origin-top-center relative mt-1.5 h-[--reka-navigation-menu-viewport-height] w-full overflow-hidden rounded-md border bg-popover text-popover-foreground shadow data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-90 md:w-[--reka-navigation-menu-viewport-width]',
          props.class,
        )
      "
    />
  </div>
</template>
