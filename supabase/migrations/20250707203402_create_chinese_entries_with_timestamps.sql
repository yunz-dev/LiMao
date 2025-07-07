-- Create the table with a composite primary key and default timestamps
CREATE TABLE chinese_entries (
    traditional TEXT NOT NULL,
    simplified TEXT NOT NULL,
    pronunciation TEXT NOT NULL,
    definitions TEXT[] NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Define a composite primary key using the traditional and simplified columns.
    PRIMARY KEY (traditional, simplified)
);

-- Create a reusable function to handle updating the updated_at column
CREATE OR REPLACE FUNCTION public.handle_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create a trigger that fires before each update on the chinese_entries table
CREATE TRIGGER on_chinese_entries_updated
BEFORE UPDATE ON public.chinese_entries
FOR EACH ROW
EXECUTE FUNCTION public.handle_updated_at();
