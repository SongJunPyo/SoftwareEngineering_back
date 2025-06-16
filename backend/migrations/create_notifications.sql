CREATE TABLE IF NOT EXISTS public.notifications (
    notification_id serial NOT NULL,
    user_id integer NOT NULL,
    type text NOT NULL,
    message text NOT NULL,
    channel text NOT NULL,
    is_read boolean NOT NULL DEFAULT false,
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    related_id integer,
    CONSTRAINT notifications_pkey PRIMARY KEY (notification_id),
    CONSTRAINT notifications_user_id_fkey FOREIGN KEY (user_id)
        REFERENCES public.users (user_id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE CASCADE
); 