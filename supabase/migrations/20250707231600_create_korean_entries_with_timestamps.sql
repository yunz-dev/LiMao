-- Create the table with appropriate fields and default timestamps
CREATE TABLE korean_entries (
    word TEXT NOT NULL,
    romaja TEXT,
    pos TEXT,
    defs TEXT[],
    conj TEXT[],       -- optional
    notes TEXT[],      -- optional
    syns TEXT[],       -- optional
    tags TEXT[],       -- optional
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Define a composite primary key using the word
    PRIMARY KEY (word)
);

-- Reuse or create the updated_at trigger function
CREATE OR REPLACE FUNCTION public.handle_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create a trigger to auto-update `updated_at` before each update
CREATE TRIGGER on_korean_entries_updated
BEFORE UPDATE ON public.korean_entries
FOR EACH ROW
EXECUTE FUNCTION public.handle_updated_at();
