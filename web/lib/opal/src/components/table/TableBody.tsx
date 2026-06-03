"use client";

import {
  SortableContext,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import type { WithoutStyles } from "@opal/types";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface DraggableProps {
  sortableItems: string[];
  isEnabled: boolean;
}

interface TableBodyProps extends WithoutStyles<
  React.HTMLAttributes<HTMLTableSectionElement>
> {
  ref?: React.Ref<HTMLTableSectionElement>;
  /** DnD context props from useDraggableRows — enables drag-and-drop reordering */
  dndSortable?: DraggableProps;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

function TableBody({ ref, dndSortable, ...props }: TableBodyProps) {
  if (dndSortable?.isEnabled) {
    return (
      <SortableContext
        items={dndSortable.sortableItems}
        strategy={verticalListSortingStrategy}
      >
        <tbody ref={ref} {...props} />
      </SortableContext>
    );
  }

  return <tbody ref={ref} {...props} />;
}

export default TableBody;
export type { TableBodyProps, DraggableProps };
