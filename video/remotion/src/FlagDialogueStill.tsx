import React from 'react';
import {Freeze} from 'remotion';
import {z} from 'zod';
import {
  FlagDialogue,
  flagDialogueSchema,
  type FlagDialogueProps,
} from './FlagDialogue';

export const flagDialogueStillSchema = flagDialogueSchema.extend({
  frame: z.number().int().min(0).default(120),
});

export type FlagDialogueStillProps = z.infer<typeof flagDialogueStillSchema>;

export const FlagDialogueStill: React.FC<FlagDialogueStillProps> = ({
  frame,
  ...props
}) => {
  const stillProps: FlagDialogueProps = {
    ...props,
    renderAudio: false,
  };

  return (
    <Freeze frame={frame}>
      <FlagDialogue {...stillProps} />
    </Freeze>
  );
};
