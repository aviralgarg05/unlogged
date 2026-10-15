// The registry this dashboard runs with: AG's default widgets plus ours.
//
// Studio is generic over a registry, and a custom widget only type-checks once the registry
// declares it. Everything downstream — AgStudio, createWidgets, the api handle — is
// parameterised with this.

import type { AgDefaultWidgetDefinition, AgWidgetData, AgWidgetDataFormat } from 'ag-studio';
import type { AgRegistry, AgWidgetDefinition } from 'ag-studio-react';

/** Which verdict fields the widget reads. One fieldset, mapped by name. */
export type EvidenceMapping = { rows: unknown };

export type EvidenceFormat = AgWidgetDataFormat<unknown>;

/** The widget's saved state. `type` is the discriminator the page state unions on. */
export interface EvidenceState extends AgWidgetData<EvidenceMapping, EvidenceFormat> {
  type: 'evidence-card';
}

export type EvidenceWidget = AgWidgetDefinition<'evidence-card', EvidenceState, EvidenceState>;

export interface UnloggedRegistry extends AgRegistry {
  widgets: readonly (AgDefaultWidgetDefinition | EvidenceWidget)[];
}
