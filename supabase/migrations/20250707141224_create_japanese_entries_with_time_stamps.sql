-- Create the table with default timestamps
CREATE TABLE japanese_entries (
    word TEXT PRIMARY KEY,
    alt_forms TEXT[],
    readings TEXT[],
    definitions TEXT[] NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create a reusable function to handle updating the updated_at column
CREATE OR REPLACE FUNCTION public.handle_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create a trigger that fires before each update on the japanese_entries table
CREATE TRIGGER on_japanese_entries_updated
BEFORE UPDATE ON public.japanese_entries
FOR EACH ROW
EXECUTE FUNCTION public.handle_updated_at();
